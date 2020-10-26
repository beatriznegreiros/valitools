import numpy as np
import matplotlib.pyplot as plt
import rasterio as rio
import earthpy.plot as ep
import matplotlib.patches as patches
from matplotlib import colors
import matplotlib
import matplotlib.transforms


def read_raster(path):
    with rio.open(path) as src:
        raster_np = src.read(1, masked=True)
    return raster_np


class RasterDataPlotter:
    def __init__(self, path):
        """
        Class of raster for plotting
        :param path: string, path of the raster to be plotted
        """
        self.path = path

    def make_hist(self, legendx, legendy, fontsize, output_file, figsize, set_ylim=None, set_xlim=None):
        """
        Create a histogram of numerical raster
        :param legendx: string, legend of the x axis of he histogram
        :param legendy: string, legend of the y axis of he histogram
        :param fontsize: integer, size of the font
        :param output_file: string, path for the output file
        :param figsize: tuple of integers, size of the width x height of the figure
        :param set_ylim: float, set the maximum limit of the y axis
        :param set_ylim: float, set the maximum limit of the x axis
        :output: saves the figure of the histogram
        """
        plt.rcParams.update({'font.size': fontsize})
        raster_np = read_raster(self.path)
        fig, ax = plt.subplots(figsize=figsize)
        _, bins, _ = ax.hist(raster_np[~raster_np.mask], bins=60)

        if set_ylim is not None:
            ax.set_ylim(set_ylim)
        if set_xlim is not None:
            ax.set_xlim(set_xlim)

        np.savetxt('trial.csv', raster_np[~raster_np.mask], delimiter=',')
        plt.xlabel(legendx)
        plt.ylabel(legendy)
        # plt.title(title)
        plt.grid(True)
        plt.subplots_adjust(left=0.17, bottom=0.15)

        # Plot line with data mean (Sfuzzy)
        plt.axvline(raster_np.mean(), color='k', linestyle='dashed', linewidth=1)
        min_ylim, max_ylim = plt.ylim()
        plt.text(raster_np.mean() * 0.70, max_ylim * 0.9, 'Sfuzzy: {:.4f}'.format(raster_np.mean()))

        # Save fig
        plt.savefig(output_file, dpi=300)
        plt.clf()

    def plot_continuous_w_window(self, output_file, xy, width, height, bounds, cmap=None, list_colors=None):
        """
        Create a figure of a raster with a zoomed window
        :param output_file: path, file path of the figure
        :param xy: tuple (x,y), origin of the zoomed window, the upper left corner
        :param width: integer, width (number of cells) of the zoomed window
        :param height: integer, height (number of cells) of the zoomed window
        :param bounds: list of float, limits for each color of the colormap
        :param cmap: string, optional, colormap to plot the raster
        :param list_colors: list of colors (str), optional, as alternative to using a colormap
        :output: saves the figure of the raster
        """
        # xy: upper left corner from the lower left corner of the picture
        raster_np = read_raster(self.path)
        print('Raster has size: ', raster_np.shape)
        fig, ax = plt.subplots(1, 2, figsize=(10, 8))
        fig.tight_layout()

        # Creates a colormap based on the given list_colors, if the cmap is not given
        if cmap is None and list_colors is not None:
            cmap = matplotlib.colors.ListedColormap(list_colors)
        elif cmap is not None and list_colors is None:
            pass
        else:
            print('Error: Insuficient number of arguments')

        norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
        ax[0].imshow(raster_np, cmap=cmap, norm=norm)
        rectangle = patches.Rectangle(xy, width, height, fill=False)
        ax[0].add_patch(rectangle)
        plt.setp(ax, xticks=[], yticks=[])

        #  Plot Patch
        box_np = raster_np[xy[1]: xy[1] + height, xy[0]: xy[0] + width]
        im = ax[1].imshow(box_np, cmap=cmap, norm=norm)
        # ax[1].axis('off')
        cbar = ep.colorbar(im, pad=0.3, size='5%')
        cbar.ax.tick_params(labelsize=20)

        fig.savefig(output_file, dpi=600, bbox_inches='tight')

    def plot_continuous_raster(self, output_file, cmap, vmax=np.nan, vmin=np.nan, box=True):
        """
        Create a figure of a continuous valued raster
        :param output_file: path, file path of the figure
        :param cmap: string, colormap to plot the raster
        :param vmax: float, optional, value maximum of the scale, this value is used in the normalization of the colormap
        :param vmin: float, optional, value minimum of the scale, this value is used in the normalization of the colormap
        :param box: boolean, if False it sets off the frame of the picture
        :output: saves the figure of the raster
        """
        raster_np = read_raster(self.path)
        fig1, ax1 = plt.subplots(figsize=(6, 8), frameon=False)
        # norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
        if np.isfinite(vmax) and np.isfinite(vmin):
            im1 = ax1.imshow(raster_np, cmap=cmap, vmax=vmax, vmin=vmin)
        else:
            im1 = ax1.imshow(raster_np, cmap=cmap, vmax=raster_np.max(), vmin=raster_np.min())
        fig1.tight_layout()
        plt.setp(ax1)
        cbar = ep.colorbar(im1, pad=0.3, size='5%')
        cbar.ax.tick_params(labelsize=15)
        if not box:
            ax1.axis('off')
        fig1.savefig(output_file, dpi=200, bbox_inches='tight')

    def plot_categorical_raster(self, output_file, labels, cmap, box=True):
        """
        Create a figure of a categorical raster
        :param output_file: path, file path of the figure
        :param labels: list of strings, labels (i.e., titles)for the categories
        :param cmap: string, colormap to plot the raster
        :param box: boolean, if False it sets off the frame of the picture
        :output: saves the figure of the raster
        """
        raster_np = read_raster(self.path)
        print('Classes identified in the raster: ', np.unique(raster_np))
        # cmap = matplotlib.colors.ListedColormap(list_colors)
        fig, ax = plt.subplots()
        im = ax.imshow(raster_np, cmap=cmap)
        ep.draw_legend(im, titles=labels)
        ax.set_axis_off()
        # plt.show()
        if not box:
            ax.axis('off')
        fig.savefig(output_file, dpi=200, bbox_inches='tight')

    def plot_categorical_w_window(self, output_file, labels, cmap, xy, width, height, box=True):
        """
        Create a figure of a categorical raster with a zoomed window
        :param output_file: path, file path of the figure
        :param labels: list of strings, labels (i.e., titles)for the categories
        :param cmap: string, colormap to plot the raster
        :param xy: tuple (x,y), origin of the zoomed window, the upper left corner
        :param width: integer, width (number of cells) of the zoomed window
        :param height: integer, height (number of cells) of the zoomed window
        :output: saves the figure of the raster
        """
        raster_np = read_raster(self.path)
        print('Classes identified in the raster: ', np.unique(raster_np))
        # cmap = matplotlib.colors.ListedColormap(list_colors)
        fig, ax = plt.subplots(1, 2)

        ax[0].imshow(raster_np, cmap=cmap)
        rectangle = patches.Rectangle(xy, width, height, fill=False)
        ax[0].add_patch(rectangle)
        plt.setp(ax, xticks=[], yticks=[])

        #  Plot Patch
        box_np = raster_np[xy[1]: xy[1] + height, xy[0]: xy[0] + width]
        im = ax[1].imshow(box_np, cmap=cmap)
        cbar = ep.draw_legend(im, titles=labels)
        # cbar.ax[].tick_params(labelsize=20)

        if not box:
            ax.axis('off')
        fig.savefig(output_file, dpi=700, bbox_inches='tight')