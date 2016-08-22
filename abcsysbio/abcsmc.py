import numpy
from numpy import random as rnd

import copy, time

from abcsysbio import euclidian
from abcsysbio import kernels
from abcsysbio import statistics

"""
priors: 
              a 3D list.
              The first dimension represents the number of models, the second dimension
              represents the number of parameter for a particular model and the third dimension
              represents the distribution for this parameter and has a constant length of 3.
              The first entry for each parameter is an integer number that stands for a
              specific distribution.
              
              Implemented distributions are:
              0   ---   constant parameter.
                        Example: constant parameter with value 12.3
                        [0 , 12.3 , x] , where x can be any number

              1   ---   normal distribution. 
                        Example: normal distribution in mean 10 and var 1
                        [1 , 10 , 1]

              2   ---   uniform distribution. 
                        Example: uniform distribution in the range 0.1 to 50
                        [2 , 0.1 , 50]

              3   ---   lognormal distribution.
                        Example: lognormal distribution with mean 3 and var 1.5
                        [3 , 3 , 1.5]

              Example:
              1 model with 3 parameter, the first two parameter have uniform prior between 0 and
              5, the third parameter has lognormal prior with mean 1 and varianz 3.
              [ [ [1,0,5],[1,0,5],[2,1,3] ], ]
              2 models where the first model has 2 parameter (the first is constant 3 and the 
              second is uniform between 0 and 1) and the second model has 1 lognormal parameter
              with 0 mean and varianz 0.5
              [ [ [0,3,0],[1,0,1] ] , [ [2,0,0.5],] ]

fit:      
              a 2D list of strings.
              This list contains the fitting instructions and therefore defines how to fit the
              experimental data to the systems variables. The first dimension represents the 
              models to be investigated, the second dimension represents the amount of data.
              
              Example:
              1 model with 7 species, 3 data series
              fit = [ ['species1+species2' , 'species5' , '3*species4-species7'], ]
              2 models with each 7 species, 2 data series
              fit = [ ['species1' , 'species2*species3'] , ['species1' , 'species2*species4'] ]
              
              The default value is 'None', i.e. the order of data series corresponds exactly 
              to the order of species.
"""


## distances are stored as [nparticle][nbeta][d1, d2, d3 .... ]
## trajectories are stored as [nparticle][nbeta][ species ][ times ]

class abcsmc_results:
    def __init__(self,
                 naccepted,
                 sampled,
                 rate,
                 trajectories,
                 distances,
                 margins,
                 models,
                 weights,
                 parameters,
                 epsilon):
        self.naccepted = naccepted
        self.sampled = sampled
        self.rate = rate
        self.trajectories = copy.deepcopy(trajectories)
        self.distances = copy.deepcopy(distances)
        self.margins = copy.deepcopy(margins)
        self.models = copy.deepcopy(models)
        self.weights = copy.deepcopy(weights)
        self.parameters = copy.deepcopy(parameters)
        self.epsilon = epsilon


class abcsmc:
    # instantiation
    def __init__(self,
                 models,
                 nparticles,
                 modelprior,
                 data,
                 beta,
                 nbatch,
                 modelKernel,
                 debug,
                 timing,
                 distancefn=euclidian.euclidianDistance,
                 kernel_type=1,
                 kernelfn=kernels.getKernel,
                 kernelpdffn=kernels.getPdfParameterKernel,
                 perturbfn=kernels.perturbParticle):

        self.nmodel = len(models)
        self.models = copy.copy(models)
        self.data = copy.deepcopy(data)

        self.nparticles = nparticles

        self.model_prev = [0] * nparticles
        self.weights_prev = [0] * nparticles
        self.parameters_prev = [[] for j in range(0,self.nparticles)]
        self.margins_prev = [0] * self.nmodel

        self.model_curr = [0] * nparticles
        self.weights_curr = [0] * nparticles
        self.parameters_curr = [[] for j in range(0,self.nparticles)]
        self.margins_curr = [0] * self.nmodel

        self.b = [0] * nparticles
        self.distances = []
        self.trajectories = []

        self.distancefn = distancefn
        self.kernel_type = kernel_type
        self.kernelfn = kernels.getKernel
        self.kernelpdffn = kernels.getPdfParameterKernel
        self.perturbfn = kernels.perturbParticle

        self.beta = beta
        self.dead_models = []
        self.nbatch = nbatch
        self.debug = debug
        self.timing = timing

        self.modelprior = modelprior[:]
        self.modelKernel = modelKernel
        self.kernel_aux = [0] * nparticles

        self.kernels = list()
        # self.kernels is a list of length the number of models
        # self.kernels[i] is a list of length 2 such that :
        # self.kernels[i][0] contains the index of the non constant parameters for the model i
        # self.kernels[i][1] contains the information required to build the kernel and given by the input_file
        # self.kernels[i][2] is filled in during the kernelfn step and contains values/matrix etc depending ont he kernel
        kernel_option = list()
        for i in range(self.nmodel):
            if self.kernel_type == 4:
                # Option for K nearest neigbours - user should be able to specify
                kernel_option.append(int(nparticles / 4))
            else:
                kernel_option.append(0)

        # get the list of parameters with non constant prior
        for i in range(self.nmodel):
            ind = list()
            for j in range(self.models[i].nparameters):
                if not (self.models[i].prior[j][0] == 0):
                    ind.append(j)
            # kernel info will get set after first population
            self.kernels.append([ind, kernel_option[i], 0])

            # get
        self.special_cases = [0] * self.nmodel
        if self.kernel_type == 1:

            for m in range(self.nmodel):
                all_uniform = True
                for j in range(self.models[m].nparameters):
                    if not (self.models[m].prior[j][0] == 0 or self.models[m].prior[j][0] == 2):
                        all_uniform = False
                if all_uniform:
                    self.special_cases[m] = 1
                    print "### Found special kernel case 1 for model ", m, "###"

        self.hits = []
        self.sampled = []
        self.rate = []
        self.dead_models = []
        self.sample_from_prior = True

    def run_fixed_schedule(self, epsilon, io):
        all_start_time = time.time()
        for pop in range(len(epsilon)):
            start_time = time.time()
            if pop == 0 and self.sample_from_prior:
                results = self.iterate_one_population(epsilon[pop], prior=True)
            else:
                results = self.iterate_one_population(epsilon[pop], prior=False)
            end_time = time.time()

            io.write_pickled(self.nmodel, self.model_prev, self.weights_prev, self.parameters_prev, self.margins_prev,
                             self.kernels)
            io.write_data(pop, results, end_time - start_time, self.models, self.data)

            if self.debug == 1:
                print "### population ", pop + 1
                print "\t sampling steps / acceptance rate :", self.sampled[pop], "/", self.rate[pop]
                print "\t model marginals                  :", self.margins_prev

                if len(self.dead_models) > 0:
                    print "\t dead models                      :", self.dead_models
                if self.timing:
                    print "\t timing:                          :", end_time - start_time

        if self.timing:
            print "#### final time:", time.time() - all_start_time

    def run_automated_schedule(self, final_epsilon, alpha, io):
        all_start_time = time.time()

        done = False
        final = False
        pop = 0
        epsilon = [1e10] * len(final_epsilon)

        while not done:
            if final:
                done = True

            start_time = time.time()
            if pop == 0 and self.sample_from_prior:
                results = self.iterate_one_population(epsilon, prior=True)
            else:
                results = self.iterate_one_population(epsilon, prior=False)
            end_time = time.time()

            io.write_pickled(self.nmodel, self.model_prev, self.weights_prev, self.parameters_prev, self.margins_prev,
                             self.kernels)
            io.write_data(pop, results, end_time - start_time, self.models, self.data)

            final, epsilon = self.compute_next_epsilon(results, epsilon, final_epsilon, alpha)

            if self.debug == 1:
                print "### population ", pop + 1
                print "\t sampling steps / acceptance rate :", self.sampled[pop], "/", self.rate[pop]
                print "\t model marginals                  :", self.margins_prev
                print "\t next epsilon                     :", epsilon

                if len(self.dead_models) > 0:
                    print "\t dead models                      :", self.dead_models
                if self.timing:
                    print "\t timing:                          :", end_time - start_time

            pop += 1

        if self.timing:
            print "#### final time:", time.time() - all_start_time

        return

    def compute_next_epsilon(self, results, this_epsilon, target_epsilon, alpha):
        nepsilon = len(target_epsilon)
        # print "compute_next_epsilon : this_epsilon, target_epsilon, nepsilon:", this_epsilon, target_epsilon, nepsilon

        distance_values = []
        for i in range(self.nparticles):
            for j in range(self.beta):
                distance_values.append(results.distances[i][j])

        # Important to remember that the initial sort on distance is done on the first distance value
        distance_values = numpy.sort(distance_values, axis=0)
        ntar = int(alpha * self.nparticles)
        # print distance_values

        # this_epsilon is the current value
        # new epsilon is the calculated epsilon
        # ret_epsilon is the epsilon that we will return
        # target_epsilon is the target
        # finished indicates if this is the last population to run

        new_epsilon = [round(distance_values[ntar, ne], 4) for ne in range(nepsilon)]
        ret_epsilon = [0 for i in range(nepsilon)]

        # Set the next epsilon as the new calculated epsilon
        for ne in range(nepsilon):
            ret_epsilon[ne] = new_epsilon[ne]

        # See if we are finished by reaching the target epsilon
        finished = 1
        for ne in range(nepsilon):
            # for any statistics that are at the level of, or below the target, set the returned value to be equal to the target
            if ret_epsilon[ne] < target_epsilon[ne] or numpy.fabs(ret_epsilon[ne] - target_epsilon[ne]) < 1e-3:
                ret_epsilon[ne] = target_epsilon[ne]
                finished *= 1
            else:
                finished *= 0

        # At this point we have a new epsilon to return and we should know if we are finished
        print "new/ret epsilon:", new_epsilon, ret_epsilon, finished

        return finished, ret_epsilon

    def run_simulations(self, io):

        naccepted = 0
        sampled = 0

        while naccepted < self.nparticles:
            if self.debug == 2:
                print "\t****batch"
            sampled_models = self.sampleTheModelFromPrior()
            sampled_params = self.sampleTheParameterFromPrior(sampled_models)

            accepted_index, distances, traj = self.simulate_and_compare_to_data(sampled_models, sampled_params,
                                                                                this_epsilon=0, do_comp=False)

            for i in range(self.nbatch):
                if naccepted < self.nparticles:
                    sampled += 1

                if naccepted < self.nparticles and accepted_index[i] > 0:

                    self.model_curr[naccepted] = sampled_models[i]
                    if self.debug == 2:
                        print "\t****accepted", i, accepted_index[i], sampled_models[i]

                    for p in range(self.models[sampled_models[i]].nparameters):
                        self.parameters_curr[naccepted].append(sampled_params[i][p])

                    self.b[naccepted] = accepted_index[i]
                    self.trajectories.append(copy.deepcopy(traj[i]))
                    self.distances.append(copy.deepcopy(distances[i]))

                    naccepted += 1

            print "#### current naccepted:", naccepted

            if self.debug == 2:
                print "\t****end  batch naccepted/sampled:", naccepted, sampled

        # Finished loop over particles
        if self.debug == 2:
            print "**** end of population naccepted/sampled:", naccepted, sampled

        results = abcsmc_results(naccepted, sampled, naccepted / float(sampled), self.trajectories, self.distances,
                                 0, self.model_curr, 0, self.parameters_curr, 0)

        io.write_data_simulation(0, results, 0, self.models, self.data)

    def iterate_one_population(self, next_epsilon, prior):
        if self.debug == 2:
            print "\n\n****iterate_one_population: next_epsilon, prior", next_epsilon, prior

        naccepted = 0
        sampled = 0

        while naccepted < self.nparticles:
            if self.debug == 2:
                print "\t****batch"
            if not prior:
                sampled_models = self.sampleTheModel()
                sampled_params = self.sampleTheParameter(sampled_models)
            else:
                sampled_models = self.sampleTheModelFromPrior()
                sampled_params = self.sampleTheParameterFromPrior(sampled_models)

            accepted_index, distances, traj = self.simulate_and_compare_to_data(sampled_models, sampled_params,
                                                                                next_epsilon)

            for i in range(self.nbatch):
                if naccepted < self.nparticles:
                    sampled += 1

                if naccepted < self.nparticles and accepted_index[i] > 0:

                    self.model_curr[naccepted] = sampled_models[i]
                    if self.debug == 2:
                        print "\t****accepted", i, accepted_index[i], sampled_models[i]

                    for p in range(self.models[sampled_models[i]].nparameters):
                        self.parameters_curr[naccepted].append(sampled_params[i][p])

                    self.b[naccepted] = accepted_index[i]
                    self.trajectories.append(copy.deepcopy(traj[i]))
                    self.distances.append(copy.deepcopy(distances[i]))

                    naccepted += 1
            print "#### current naccepted:", naccepted

            if self.debug == 2:
                print "\t****end  batch naccepted/sampled:", naccepted, sampled

        # Finished loop over particles
        if self.debug == 2:
            print "**** end of population naccepted/sampled:", naccepted, sampled

        if not prior:
            self.compute_particle_weights()
        else:
            for i in range(self.nparticles):
                self.weights_curr[i] = self.b[i]

        self.normalizeWeights()
        self.update_model_marginals()

        if self.debug == 2:
            print "**** end of population: particles"
            for i in range(self.nparticles):
                print i, self.weights_curr[i], self.model_curr[i], self.parameters_curr[i]
            print self.margins_curr

        #
        # Prepare for next population
        # 
        self.margins_prev = self.margins_curr[:]
        self.weights_prev = self.weights_curr[:]
        self.model_prev = self.model_curr[:]
        self.parameters_prev = []
        for i in range(self.nparticles):
            self.parameters_prev.append(self.parameters_curr[i][:])

        self.model_curr = [0] * self.nparticles
        self.weights_curr = [0] * self.nparticles
        self.parameters_curr = [[] for j in range(0,self.nparticles)]
        self.margins_curr = [0] * self.nmodel

        self.b = [0] * self.nparticles

        #
        # Check for dead models
        #
        self.dead_models = []
        for j in range(self.nmodel):
            if self.margins_prev[j] < 1e-6:
                self.dead_models.append(j)

        #
        # Compute kernels
        #
        for mod in range(self.nmodel):
            this_model_index = numpy.arange(self.nparticles)[numpy.array(self.model_prev) == mod]
            this_population = numpy.zeros([len(this_model_index), self.models[mod].nparameters])
            this_weights = numpy.zeros(len(this_model_index))

            # if we have just sampled from the prior we shall initialise the kernels using all available particles
            if prior:
                for it in range(len(this_model_index)):
                    this_population[it, :] = self.parameters_prev[this_model_index[it]][:]
                    this_weights[it] = self.weights_prev[this_model_index[it]]
                tmp_kernel = self.kernelfn(self.kernel_type, self.kernels[mod], this_population, this_weights)
                self.kernels[mod] = tmp_kernel[:]

            else:
                # only update the kernels if there are > 5 particles
                if len(this_model_index) > 5:
                    for it in range(len(this_model_index)):
                        this_population[it, :] = self.parameters_prev[this_model_index[it]][:]
                        this_weights[it] = self.weights_prev[this_model_index[it]]
                    tmp_kernel = self.kernelfn(self.kernel_type, self.kernels[mod], this_population, this_weights)
                    self.kernels[mod] = tmp_kernel[:]

        #
        # Kernel auxilliary information
        #
        self.kernel_aux = kernels.getAuxilliaryInfo(self.kernel_type, self.model_prev, self.parameters_prev,
                                                    self.models, self.kernels)[:]

        self.hits.append(naccepted)
        self.sampled.append(sampled)
        self.rate.append(naccepted / float(sampled))

        results = abcsmc_results(naccepted,
                                 sampled,
                                 naccepted / float(sampled),
                                 self.trajectories,
                                 self.distances,
                                 self.margins_prev,
                                 self.model_prev,
                                 self.weights_prev,
                                 self.parameters_prev,
                                 next_epsilon)

        self.trajectories = []
        self.distances = []

        return results

    # end of iterate_one_population

    def fill_values(self, particle_data):
        # particle data comprises of [model_pickled, weights_pickled, parameters_pickled, margins_pickled, kernel]
        self.model_prev = particle_data[0][:]
        self.weights_prev = particle_data[1][:]
        self.margins_prev = particle_data[3][:]

        self.parameters_prev = []
        for it in range(len(particle_data[2])):
            self.parameters_prev.append(particle_data[2][it][:])

        self.kernels = []
        for i in range(self.nmodel):
            self.kernels.append([])
            for j in range(len(particle_data[4][i])):
                self.kernels[i].append(particle_data[4][i][j])

        self.sample_from_prior = False

    def simulate_and_compare_to_data(self, sampled_models, sampled_params, this_epsilon, do_comp=True):
        # Here do the simulations for each model together
        if self.debug == 2:
            print '\t\t\t***simulate_and_compare_to_data'

        ret = [0 for it in range(self.nbatch)]
        traj = [[] for it in range(self.nbatch)]
        distances = [[] for it in range(self.nbatch)]

        n_to_simulate = [0 for it in range(self.nmodel)]
        mods = numpy.array(sampled_models)

        for m in range(self.nmodel):
            # Get the indices for this model and extract
            # the relevant parameters 

            # create a mapping to the original position
            mapping = numpy.arange(self.nbatch)[mods == m]
            if self.debug == 2:
                print "\t\t\tmodel / mapping:", m, mapping
            n_to_simulate = len(mapping)

            if n_to_simulate > 0:
                # simulate this chunk
                this_model_parameters = []
                for i in range(n_to_simulate):
                    this_model_parameters.append(sampled_params[mapping[i]])

                # print "this_model_parameters", this_model_parameters
                sims = self.models[m].simulate(this_model_parameters, self.data.timepoints, n_to_simulate, self.beta)
                if self.debug == 2:
                    print '\t\t\tsimulation dimensions:', sims.shape

                for i in range(n_to_simulate):
                    # store the trajectories and distances in a list of length beta
                    this_dist = []
                    this_traj = []

                    for k in range(self.beta):
                        samplePoints = sims[i, k, :, :]
                        points = howToFitData(self.models[m].fit, samplePoints)
                        if do_comp:
                            distance = self.distancefn(points, self.data.values, this_model_parameters[i], m)
                            dist = evaluateDistance(distance, this_epsilon)
                        else:
                            distance = 0
                            dist = True

                        this_dist.append(distance)
                        this_traj.append(points)

                        if dist:
                            ret[mapping[i]] += 1

                        if self.debug == 2:
                            print '\t\t\tdistance/this_epsilon/mapping/b:', distance, this_epsilon, \
                        mapping[i], ret[mapping[i]]

                    traj[mapping[i]] = copy.deepcopy(this_traj)
                    distances[mapping[i]] = copy.deepcopy(this_dist)

        return ret[:], distances, traj

    def sampleTheModelFromPrior(self):
        """
        Returns a list of model numbers, of length self.nbatch, drawn from a categorical distribution with probabilities
         self.modelprior

        """
        models = [0] * self.nbatch
        if self.nmodel > 1:
            for i in range(self.nbatch):
                models[i] = statistics.w_choice(range(self.nmodel), self.modelprior)

        return models

    def sampleTheModel(self):
        """
        Returns a list of model numbers, of length self.nbatch, obtained by sampling from a categorical distribution
        with probabilities self.modelprior, and then perturbing with a uniform model perturbation kernel.
        """

        models = [0] * self.nbatch

        if self.nmodel > 1:
            # Sample models from prior distribution
            for i in range(self.nbatch):
                models[i] = statistics.w_choice(range(self.nmodel), self.margins_prev)

            # perturb models
            if len(self.dead_models) < self.nmodel - 1:

                for i in range(self.nbatch):
                    u = rnd.uniform(low=0, high=1)

                    if u > self.modelKernel:
                        # sample randomly from other (non dead) models
                        not_available = set(self.dead_models[:])
                        not_available.add(models[i])

                        available_indexes = numpy.array(list(set(range(0, self.nmodel)) - not_available))
                        rnd.shuffle(available_indexes)
                        perturbed_model = available_indexes[0]

                        models[i] = perturbed_model
        return models[:]

    def sampleTheParameterFromPrior(self, sampled_models):
        """
        For each model whose index is in sampled_models, draw a sample of the corresponding parameters.

        Parameters
        ----------
        sampled_models : a list of model indexes, of length self.nbatch

        Returns
        -------
        a list of length self.nbatch, each entry of which is a list of parameter samples (whose length is model.nparameters
            for the corresponding model)

        """
        samples = []

        for i in range(self.nbatch):
            model = self.models[sampled_models[i]]
            sample = [0] * model.nparameters

            for param in range(model.nparameters):
                if model.prior[param][0] == 0:
                    sample[param] = model.prior[param][1]

                if model.prior[param][0] == 1:
                    sample[param] = rnd.normal(loc=model.prior[param][1], scale=numpy.sqrt(model.prior[param][2]))

                if model.prior[param][0] == 2:
                    sample[param] = rnd.uniform(low=model.prior[param][1], high=model.prior[param][2])

                if model.prior[param][0] == 3:
                    sample[param] = rnd.lognormal(mean=model.prior[param][1], sigma=numpy.sqrt(model.prior[param][2]))

            samples.append(sample[:])

        return samples

    def sampleTheParameter(self, sampled_models):
        """
        For each model index in sampled_models, sample a set of parameters by sampling a particle from
        the corresponding model (with probability biased by the particle weights); if this gives parameters with
        probability <=0 the process is repeated.

        Parameters
        ----------
        sampled_models : a list of model indexes, of length self.nbatch


        Returns
        -------
        a list of length self.nbatch, each entry of which is a list of parameter samples (whose length is model.nparameters
            for the corresponding model)

        """
        if self.debug == 2:
            print "\t\t\t***sampleTheParameter"
        samples = []

        for i in range(self.nbatch):
            model = self.models[sampled_models[i]]
            model_num = sampled_models[i]

            num_params = model.nparameters
            sample = [0] * num_params

            prior_prob = -1
            while prior_prob <= 0:

                # sample putative particle from previous population
                particle = sample_particle_from_model(self.nparticles, model_num, self.margins_prev, self.model_prev,
                                               self.weights_prev)

                for nn in range(num_params):
                    sample[nn] = self.parameters_prev[particle][nn]

                prior_prob = self.perturbfn(sample, model.prior, self.kernels[model_num],
                                            self.kernel_type, self.special_cases[model_num])

                if self.debug == 2:
                    print "\t\t\tsampled p prob:", prior_prob
                    print "\t\t\tnew:", sample
                    print "\t\t\told:", self.parameters_prev[particle]

            samples.append(sample)

        return samples

    def compute_particle_weights(self):
        """
        Calculate the weight of each particle.
        This is given by $w_t^i = \frac{\pi(M_t^i, \theta_t^i) P_{t-1}(M_t^i = M_{t-1}) }{S_1 S_2 }$, where
        $S_1 = \sum_{j \in M} P_{t-1}(M^j_{t-1}) KM_t(M_t^i | M^j_{t-1})$ and
        $S_2 = \sum_{k \in M_t^i = M_{t-1}} w^k_{t-1} K_{t, M^i}(\theta_t^i | \theta_{t-1}^k)$

        (See p.4 of SOM to 'Bayesian design of synthetic biological systems', except that here we have moved model
        marginal out of S2 into a separate term)
        """
        if self.debug == 2:
            print "\t***computeParticleWeights"

        for k in range(self.nparticles):
            this_model = self.model_curr[k]
            this_param = self.parameters_curr[k]

            model_prior = self.modelprior[this_model]

            particle_prior = 1
            for n in range(0, len(self.parameters_curr[k])):
                x = 1.0
                if self.models[this_model].prior[n][0] == 0:
                    x = 1

                if self.models[this_model].prior[n][0] == 1:
                    x = statistics.getPdfGauss(self.models[this_model].prior[n][1],
                                               numpy.sqrt(self.models[this_model].prior[n][2]),
                                               this_param[n])

                if self.models[this_model].prior[n][0] == 2:
                    x = statistics.getPdfUniform(self.models[this_model].prior[n][1],
                                                 self.models[this_model].prior[n][2],
                                                 this_param[n])

                if self.models[this_model].prior[n][0] == 3:
                    x = statistics.getPdfLognormal(self.models[this_model].prior[n][1],
                                                   numpy.sqrt(self.models[this_model].prior[n][2]),
                                                   this_param[n])
                particle_prior = particle_prior * x

            # self.b[k] is an indicator variable recording whether the simulation corresponding to particle k was accepted
            numerator = self.b[k] * model_prior * particle_prior

            S1 = 0
            for i in range(self.nmodel):
                S1 += self.margins_prev[i] * getPdfModelKernel(this_model, i, self.modelKernel, self.nmodel,
                                                                    self.dead_models)
            S2 = 0
            for j in range(self.nparticles):
                if int(this_model) == int(self.model_prev[j]):

                    if self.debug == 2:
                        print "\tj, weights_prev, kernelpdf", j, self.weights_prev[j],
                        self.kernelpdffn(this_param, self.parameters_prev[j], self.models[this_model].prior,
                                         self.kernels[this_model], self.kernel_aux[j], self.kernel_type)
                    S2 += self.weights_prev[j] * self.kernelpdffn(this_param, self.parameters_prev[j],
                                                                     self.models[this_model].prior,
                                                                     self.kernels[this_model], self.kernel_aux[j],
                                                                     self.kernel_type)

                if self.debug == 2:
                    print "\tnumer/S1/S2/m(t-1) : ", numerator, S1, S2, self.margins_prev[this_model]

            self.weights_curr[k] = self.margins_prev[this_model] * numerator / (S1 * S2)

    def normalizeWeights(self):
        """
        Normalize weights by dividing each by the total.
        """
        n = sum(self.weights_curr)
        for i in range(self.nparticles):
            self.weights_curr[i] /= float(n)

    def update_model_marginals(self):
        """
        Re-calculate the marginal probability of each model as the sum of the weights of the corresponding particles.
        """
        for model in range(self.nmodel):
            self.margins_curr[model] = 0
            for particle in range(self.nparticles):
                if int(self.model_curr[particle]) == int(model):
                    self.margins_curr[model] += self.weights_curr[particle]


def sample_particle_from_model(nparticle, selected_model, margins_prev, model_prev, weights_prev):
    """
    Select a particle from those in the previous generation whose model was the currently selected model, weighted by
    their previous weight.

    Parameters
    ----------
    nparticle : number of particles
    selected_model : index of the currently selected model
    margins_prev : the marginal probability of the selected model at the previous iteration (nb. this is the sum of the
        weights of the corresponding particles)
    model_prev : list recording the model index corresponding to each particle from the previous iteration
    weights_prev : list recording the weight of each particle from the previous iteration

    Returns
    -------
    the index of the selected particle
    """
    u = rnd.uniform(low=0, high=margins_prev[selected_model])
    F = 0

    for i in range(0, nparticle):
        if int(model_prev[i]) == int(selected_model):
            F = F + weights_prev[i]
            if F > u:
                break
    return i


def howToFitData(fitting_instruction, samplePoints):
    """
    Given the results of a simulation, evaluate given functions of the state variables of the model.

    This accounts for the correspondance between species defined in the model being simulated and the experimental data
    being fit.

    Parameters
    ----------
    fitting_instruction : list of functions, one per dimension of the data to be fitted. Each is a string representation
        of an expression of the state variables of the model; dimension n  is represented by 'samplePoints[:,n];.

    samplePoints : a numpy.ndarray of simulation results, with shape (number_timepoints, model_dimension)

    Returns
    -------
    transformed_points : a numpy.ndarray of transformed simulation results, with shape (number_timepoints, data_dimension)

    """

    if fitting_instruction is not None:
        transformed_points = numpy.zeros([len(samplePoints), len(fitting_instruction)])
        for i in range(len(fitting_instruction)):
            transformed_points[:, i] = eval(fitting_instruction[i])
    else:
        transformed_points = samplePoints

    return transformed_points[:]


def getPdfModelKernel(new_model, old_model, modelK, num_models, num_dead_models):
    """
    Returns the probability of model number m0 being perturbed into model number m (assuming neither is dead).

    This assumes a uniform model perturbation kernel: with probability modelK the model is not perturbed; with
    probability (1-modelK) it is replaced by a model randomly chosen from the non-dead models (including the current
    model).

    Parameters
    ----------
    new_model : index of next model
    old_model : index of previous model
    modelK : model (non)-perturbation probability
    num_models : total number of models
    num_dead_models : number of models which are 'dead'
    """

    ndead = len(num_dead_models)

    if ndead == num_models - 1:
        return 1.0
    else:
        if new_model == old_model:
            return modelK
        else:
            return (1 - modelK) / (num_models - ndead)


def evaluateDistance(distance, epsilon):
    """
    Return true if each element of distance is less than the corresponding entry of epsilon (and non-negative)

    Parameters
    ----------
    distance : list of distances
    epsilon : list of maximum acceptable distances

    """

    accepted = False
    for i in range(len(epsilon)):
        if epsilon[i] >= distance[i] >= 0:
            accepted = True
        else:
            accepted = False
            break
    return accepted
