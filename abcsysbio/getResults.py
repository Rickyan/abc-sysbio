import numpy as np
import matplotlib
import matplotlib.pylab as plt
import abcsmc
import math

from matplotlib.ticker import FormatStrFormatter


# weighted histogramming
def bin_data(d, w, nbins):
    d_max = np.max(d)
    d_min = np.min(d) - 1e-6  # ensures that the lowest entry is included in the first bin
    bin_width = (d_max - d_min) / nbins

    bin_l = np.array([d_min + i * bin_width for i in range(nbins)])
    bin_u = np.array([d_min + (i + 1) * bin_width for i in range(nbins)])
    bin_c = np.array([bin_l[i] + bin_width / 2 for i in range(nbins)])

    count = np.zeros([nbins])

    for k in range(len(d)):
        kd = d[k]
        kw = w[k]

        for i in range(nbins):
            if bin_l[i] < kd <= bin_u[i]:
                count[i] = count[i] + kw
                break

    return [bin_c, count]


def matrix_to_text_file(matrix, filename, model, eps):
    """
    Write the part of a three dimensional matrix indexed by model and eps
    to a text file

    Parameters
    ----------

    matrix:

            A three-dimensional matrix
            
    filename:

            A string, the name of the file to be written

    model:

            An integer
            
    eps:

            An integer
            
    """

    out_file = open(filename + ".txt", "w")
    for particle in range(len(matrix[model][eps][0])):
        for param in range(len(matrix[model][eps])):
            out_file.write(repr(matrix[model][eps][param][particle]) + " ")
        out_file.write("\n")
    out_file.close()


def print_model_distribution(matrix, eps, filename='model_distribution.txt'):
    """
    Write the contents of a two-dimensional matrix indexed by
    eps to a text file.
    
    Parameters
    ----------

    matrix:

            A two-dimensional matrix

    eps:

            An integer

    filename:

            String.
            The name of the text file to be written.
    """

    out_file = open(filename, "w")
    for j in range(eps + 1):
        for i in range(len(matrix[0])):
            out_file.write(repr(matrix[j][i]) + " ")
        out_file.write("\n")
    out_file.close()


def plot_data(data, filename):
    plt.subplot(111)
    plt.clf()
    plt.plot(data.timepoints, data.values, 'o')
    plt.xlabel('time')
    plt.ylabel('Unit')
    plt.savefig(filename)
    matplotlib.pylab.clf()


def plot_time_series2(pars, data, beta, filename, traj2, plotdata=True):
    """
    Plot simulated trajectories from the model with accepted parameters.
        
    Parameters
    ----------

    pars:
            2D list of parameters for plotting to be done

    data:

            data object

    beta : ?

    filename:

            Name of the output file to write to.

    traj2

    plotdata:

            Boolean
            Whether or not to plot the data over the trajectories.

    """

    nsim = len(pars)
    plt.subplot(111)
    plt.clf()
    for i in range(nsim):
        for j in range(beta):
            points_sim = traj2[i][j]
            plt.plot(data.timepoints, points_sim)

    if plotdata:
        plt.plot(data.timepoints, data.values, 'o')
        plt.xlabel('time')
        plt.ylabel('Unit')

    plt.savefig(filename)
    matplotlib.pylab.clf()


def plot_time_series(model, pars, data, beta, filename, plotdata=True):
    """
    Plot simulated trajectories from the model with accepted parameters.
        
    Parameters
    ----------

    model:

            model object

    pars:
            2D list of parameters for plotting to be done
    
    data:

            data object

    beta
   
    filename:

            Name of the output file to write to.

    plotdata:

            Boolean
            Whether or not to plot the data over the trajectories.

    """

    nsim = len(pars)
    sims = model.simulate(pars, data.timepoints, nsim, beta=beta)

    plt.subplot(111)
    plt.clf()
    for i in range(nsim):
        for j in range(beta):
            points = sims[i, j, :, :]
            points_sim = abcsmc.transform_data_for_fitting(model.fit, points)
            plt.plot(data.timepoints, points_sim)

    if plotdata:
        plt.plot(data.timepoints, data.values, 'o')
        plt.xlabel('time')
        plt.ylabel('Unit')

    plt.savefig(filename)
    matplotlib.pylab.clf()


def get_all_histograms(matrix, weights, population=1, plot_name='AllScatterPlots', model=1):
    """
    Plot weighted histograms.
    
    Parameters
    ----------

    matrix:

            Matrix of data

    weights:

            Weights to assign to data


    population:

            Integer, to index matrix with required population

    plot_name:

            String.
            Name for the saved plot

    model:

            Integer, to index matrix with required model.

    """

    matplotlib.pylab.clf()
    npar = len(matrix[int(model) - 1][0])

    # Maximum plots per page is 16
    # If we are over this then require multiple plots
    multi = False
    if npar > 16:
        multi = True

    if not multi:
        # print "******************* DOING SINGLE"
        # In the below max1 refers to the number of rows
        # and max2 refers to the number of columns ie max2 x max1

        # Lets check to see whether we have more than four parameters
        # If so we just make the plots 1 x npar

        max1 = 4.0
        if max1 > npar:
            max1 = npar

        dim = math.ceil(npar / max1)

        if dim == 1:
            max1 = 2
            max2 = 2
        elif max1 > dim:
            max2 = dim
        else:
            max2 = max1

        num_plots = math.ceil(dim / max2)

        for p in range(int(num_plots)):
            start = p * max1 ** 2
            end = p * max1 * max2 + max1 * max2
            for i in range(int(start), int(end)):
                if i >= len(matrix[int(model) - 1][0]):
                    break
                plt.subplot(max1, max2, i - start + 1)
                plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.6, hspace=0.5)
                x = matrix[int(model) - 1][int(population) - 1][i]
                w = weights[int(model) - 1][int(population) - 1][i]
                bins = 20.0
                if not (len(x) == 0):
                    plt.cla()

                    histogram_x, histogram_y = bin_data(x, w, int(bins))

                    max_x = max(histogram_x)
                    min_x = min(histogram_x)
                    range_x = max_x - min_x

                    plt.bar(histogram_x, histogram_y, color='#1E90FF', width=range_x / bins, align='center')
                    plt.xlabel('parameter ' + repr(i + 1), size='xx-small')

                    xmin, xmax = plt.xlim()
                    ymin, ymax = plt.ylim()

                    ax = plt.gca()

                    if (xmax - xmin) < 0.1 or (xmax - xmin) >= 1000:
                        x_formatter = FormatStrFormatter('%0.1e')
                    else:
                        x_formatter = FormatStrFormatter('%0.2f')
                    ax.xaxis.set_major_formatter(x_formatter)

                    y_formatter = FormatStrFormatter('%i')
                    ax.yaxis.set_major_formatter(y_formatter)

                    plt.axis([xmin, xmax, ymin, ymax])
                    plt.yticks((ymin, (ymin + ymax) / 2.0, ymax), size='xx-small')
                    plt.xticks((xmin, (xmin + xmax) / 2.0, xmax), size='xx-small')

            plt.savefig(plot_name)
            matplotlib.pylab.clf()
            plt.subplot(111)

    else:

        s_num = 1
        p_num = 1
        for i in range(npar):
            plt.subplot(4, 4, s_num)
            plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.6, hspace=0.5)
            x = matrix[int(model) - 1][int(population) - 1][i]
            w = weights[int(model) - 1][int(population) - 1][i]

            plt.cla()
            bins = 20
            histogram_x, histogram_y = bin_data(x, w, int(bins))

            max_x = max(histogram_x)
            min_x = min(histogram_x)
            range_x = max_x - min_x

            plt.bar(histogram_x, histogram_y, color='#1E90FF', width=range_x / bins, align='center')
            plt.xlabel('parameter ' + repr(i + 1), size='xx-small')

            xmin, xmax = plt.xlim()
            ymin, ymax = plt.ylim()

            ax = plt.gca()

            if (xmax - xmin) < 0.1 or (xmax - xmin) >= 1000:
                x_formatter = FormatStrFormatter('%0.1e')
            else:
                x_formatter = FormatStrFormatter('%0.2f')
            ax.xaxis.set_major_formatter(x_formatter)

            y_formatter = FormatStrFormatter('%i')
            ax.xaxis.set_major_formatter(y_formatter)

            plt.axis([xmin, xmax, ymin, ymax])
            plt.yticks((ymin, (ymin + ymax) / 2.0, ymax), size='xx-small')
            plt.xticks((xmin, (xmin + xmax) / 2.0, xmax), size='xx-small')

            s_num += 1
            if s_num == 17:
                plt.savefig(plot_name + '_' + repr(p_num))
                s_num = 1
                p_num += 1
                plt.clf()

        plt.savefig(plot_name + '_' + repr(p_num))
        plt.clf()
        plt.subplot(111)


def get_all_scatter_plots(matrix, weights, populations=(1,), plot_name='AllScatterPlots', model=1):
    """
    Plot scatter plots and histograms of data given in matrix.
    Used to plot posterior parameter distributions.

    Parameters
    ----------

    matrix:

            Matrix of data.

    weights

    populations:

            Ordered tuple of integers.
            Determines which data will be plotted.
            Used to index the matrix.
            
    plot_name:

            String
            Name for the saved plot

    model:

            Integer
            Determines which data will be plotted.
            Used to index the matrix.

    """

    matplotlib.pylab.clf()
    dim = len(matrix[int(model) - 1][0])

    my_colors = ['#000000', '#003399', '#3333FF', '#6666FF', '#990000', '#CC0033', '#FF6600', '#FFCC00', '#FFFF33',
                 '#33CC00', '#339900', '#336600']

    if len(populations) > len(my_colors):
        q = int(math.ceil(len(populations) / len(my_colors)))

        for slopes in range(q):
            my_colors.extend(my_colors)

    max1 = 4.0
    if dim <= max1:
        permutation = np.zeros([dim ** 2, 2])
        k = 0
        for i in range(1, dim + 1):
            for j in range(1, dim + 1):
                permutation[k][0] = i
                permutation[k][1] = j
                k += 1

        bin_b = 20.0
        i2 = 0
        for i in range(len(permutation)):
            plt.subplot(dim, dim, i + 1)
            plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.6, hspace=0.5)
            w = weights[int(model) - 1][int(populations[len(populations) - 1]) - 1][int(permutation[i][0]) - 1]

            for j in range(len(populations)):

                x = matrix[int(model) - 1][int(populations[j]) - 1][int(permutation[i][0]) - 1]
                y = matrix[int(model) - 1][int(populations[j]) - 1][int(permutation[i][1]) - 1]

                if permutation[i][0] == permutation[i][1]:
                    if j == len(populations) - 1:
                        plt.cla()
                        if not (len(x) == 0):
                            i2 += 1
                            histogram_x, histogram_y = bin_data(x, w, int(bin_b))

                            max_x = max(histogram_x)
                            min_x = min(histogram_x)
                            range_x = max_x - min_x
                            plt.bar(histogram_x, histogram_y, width=range_x / bin_b, color=my_colors[j], align='center')
                            plt.xlabel('parameter ' + repr(i2), size='xx-small')

                else:
                    if not (len(x) == 0):
                        plt.scatter(x, y, s=10, marker='o', c=my_colors[j], edgecolor=my_colors[j])
                        plt.ylabel('parameter ' + repr(int(permutation[i][1])), size='xx-small')
                plt.xlabel('parameter ' + repr(int(permutation[i][0])), size='xx-small')

                xmin, xmax = plt.xlim()
                ymin, ymax = plt.ylim()

                ax = plt.gca()
                if (xmax - xmin) < 0.1 or (xmax - xmin) >= 1000:
                    x_formatter = FormatStrFormatter('%0.1e')
                else:
                    x_formatter = FormatStrFormatter('%0.2f')
                ax.xaxis.set_major_formatter(x_formatter)

                if (ymax - ymin) < 0.1 or (ymax - ymin) >= 1000:
                    y_formatter = FormatStrFormatter('%0.1e')
                else:
                    y_formatter = FormatStrFormatter('%0.2f')

                if permutation[i][0] == permutation[i][1]:
                    y_formatter = FormatStrFormatter('%i')

                ax.yaxis.set_major_formatter(y_formatter)

                plt.axis([xmin, xmax, ymin, ymax])
                plt.xticks((xmin, (xmin + xmax) / 2.0, xmax), size='xx-small')
                plt.yticks((ymin, (ymin + ymax) / 2.0, ymax), size='xx-small')

        plt.savefig(plot_name)
        matplotlib.pylab.clf()
        plt.subplot(111)

    else:
        i2 = 0
        permutation = plt.zeros([dim * (dim + 1) / 2, 2])
        k = 0
        for i in range(1, dim + 1):
            for j in range(i, dim + 1):
                permutation[k][0] = i
                permutation[k][1] = j
                k += 1

        bin_b = 20.0

        dim = math.ceil(len(permutation) / max1)
        num_plots = math.ceil(dim / max1)

        for p in range(int(num_plots)):

            start = p * max1 ** 2
            end = p * max1 ** 2 + max1 ** 2
            for i in range(int(start), int(end)):
                if i >= len(permutation):
                    break
                plt.subplot(max1, max1, i - start + 1)
                plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.6, hspace=0.5)
                w = weights[int(model) - 1][int(populations[len(populations) - 1]) - 1][int(permutation[i][0]) - 1]
                for j in range(len(populations)):
                    x = matrix[int(model) - 1][int(populations[j]) - 1][int(permutation[i][0]) - 1]
                    y = matrix[int(model) - 1][int(populations[j]) - 1][int(permutation[i][1]) - 1]

                    if permutation[i][0] == permutation[i][1]:
                        if j == len(populations) - 1:
                            plt.cla()
                            if not (len(x) == 0):
                                i2 += 1

                                histogram_x, histogram_y = bin_data(x, w, int(bin_b))

                                max_x = max(histogram_x)
                                min_x = min(histogram_x)
                                range_x = max_x - min_x
                                plt.bar(histogram_x, histogram_y, color=my_colors[j], width=range_x / bin_b,
                                        align='center')
                                plt.xlabel('parameter ' + repr(i2), size='xx-small')

                    else:
                        if not (len(x) == 0):
                            plt.scatter(x, y, s=10, marker='o', c=my_colors[j], edgecolor=my_colors[j])
                            plt.ylabel('parameter ' + repr(int(permutation[i][1])), size='xx-small')
                            plt.xlabel('parameter ' + repr(int(permutation[i][0])), size='xx-small')

                    xmin, xmax = plt.xlim()
                    ymin, ymax = plt.ylim()

                    ax = plt.gca()
                    if (xmax - xmin) < 0.1 or (xmax - xmin) >= 1000:
                        x_formatter = FormatStrFormatter('%0.1e')
                    else:
                        x_formatter = FormatStrFormatter('%0.2f')
                    ax.xaxis.set_major_formatter(x_formatter)

                    if (ymax - ymin) < 0.1 or (ymax - ymin) >= 1000:
                        y_formatter = FormatStrFormatter('%0.1e')
                    else:
                        y_formatter = FormatStrFormatter('%0.2f')

                    if permutation[i][0] == permutation[i][1]:
                        y_formatter = FormatStrFormatter('%i')

                    ax.yaxis.set_major_formatter(y_formatter)

                    plt.axis([xmin, xmax, ymin, ymax])
                    plt.xticks((xmin, (xmin + xmax) / 2.0, xmax), size='xx-small')
                    plt.yticks((ymin, (ymin + ymax) / 2.0, ymax), size='xx-small')

            plt.savefig(plot_name + "_" + repr(p))
            matplotlib.pylab.clf()
            plt.subplot(111)


def get_scatter_plot(matrix, parameter, populations=(1,), plot_name='ScatterPlot', model=1):
    """
    Plot a single scatter plot of accepted parameters.

    Parameters
    ----------

    matrix:

            Matrix of accepted parameters.

    parameter:

            List of integers of length 2.
            Used to index the matrix,
            to determine which two parameters to plot against each other.

    populations:

            Tuple of integers.
            Used to index the matrix.
            Accepted parameters from these populations will be plotted.

    plot_name:

            String
            Name for the saved plot

    model:

            Integer
            Number for the model from which accepted parameters should be plotted.

    """

    matplotlib.pylab.clf()
    plt.subplot(111)

    for j in range(len(populations)):
        g = (j + 1) * ((len(populations) * 1.5) ** (-1))
        x = matrix[int(model) - 1][int(populations[j]) - 1][int(parameter[0]) - 1]
        y = matrix[int(model) - 1][int(populations[j]) - 1][int(parameter[1]) - 1]
        if not (len(x) == 0):
            plt.scatter(x, y, s=10, c=repr(g), edgecolor=repr(g))
    plt.savefig(plot_name)
    matplotlib.pylab.clf()


def get_model_distribution(matrix, epsilon, rate, plot_name='ModelDistribution'):
    """
    Plot a histogram of the posterior distributions of the models

    Parameters
    ----------

    matrix:

            Matrix containing the model distributions
            after each population.

    epsilon:

            Epsilon used for each population
            (To be displayed above the plot)

    rate:

            Acceptance rate for each population
            (To be displayed above the plot)

    plot_name:

            Prefix for file name for the saved plot.
            If the saved plot runs over multiple pages,
            each page will be saved to a separate file, with this prefix.

    """

    matplotlib.pylab.clf()
    max1 = 4.0  # must be float or double, but no integer
    if max1 > len(matrix):
        max1 = len(matrix)

    dim = math.ceil(len(matrix) / max1)

    if dim == 1:
        max1 = 2
        max2 = 2
    elif max1 > dim:
        max2 = dim
    else:
        max2 = max1

    num_plots = math.ceil(dim / max2)

    for p in range(int(num_plots)):

        start = p * max1 ** 2
        end = p * max1 * max2 + max1 * max2
        for i in range(int(start), int(end)):
            if i >= len(matrix): 
                break
            plt.subplot(max1, max2, i - start + 1)
            plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=0.6, hspace=0.8)
            left = np.arange(1, matrix.shape[1] + 1, 1)
            height = matrix[i]
            plt.bar(left, height, width=1.0, color='#1E90FF', align='center')
            xmin = 0
            xmax = matrix.shape[1] + 1
            ymin, ymax = plt.ylim()
            plt.axis([math.floor(xmin), math.ceil(xmax), 0, ymax + ymax * 0.1])
            plt.yticks(size='xx-small')
            plt.xticks(left, size='xx-small')
            plt.title("(" + repr(i + 1) + ") " + str(epsilon[i]) + "\n" + str(rate[i]), size='xx-small')
            plt.savefig(plot_name + '_' + repr(p + 1))
        matplotlib.pylab.clf()
        plt.subplot(111)
