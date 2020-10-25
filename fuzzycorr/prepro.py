try:
    import geopandas
    import ogr
    import gdal
    import rasterio as rio
    import numpy as np
    import pandas as pd
    import alphashape
    import mapclassify.classifiers as mc
    from pathlib import Path
    from pyproj import CRS
    from scipy import interpolate
except:
    print(
        'ModuleNotFoundError: Missing fundamental packages (required: geopandas, ogr, gdal, rasterio, numpy, pandas, '
        'alphashape, mapclassify, pathlib, pyproj, scipy and pykrige).')


def clip_raster(polygon, in_raster, out_raster):
    """ Clips a raster based on the given polygon
        :param polygon: string, file with path of the polygon (*.shp)
        :param in_raster: string, file and path of the input raster (*.tif)
        :param in_raster: string, file and path of the output raster (*.tif)
        :return: no output, saves the raster (*.tif) with the selected filename
    """

    gdal.Warp(out_raster, in_raster, cutlineDSName=polygon)


class PreProFuzzy:
    def __init__(self, pd, attribute, crs, nodatavalue, res=None, ulc=(np.nan, np.nan),
                 lrc=(np.nan, np.nan)):
        """ Performing pre-processing
        :param pd: pandas dataframe, can be obtained by reading the textfile as pandas dataframe
        :param attribute: string, name of the attribute to burn in the raster (ex.: deltaZ, Z)
        :param crs: string, coordinate reference system
        :param nodatavalue: float, value to indicate nodata cells
        :param res: float, resolution of the cell (cell size), is the same for x and y
        :param ulc: tuple of floats, upper left corner coordinate, optional
        :param lrc: tuple of floats, lower right corner coordinate, optional
        """

        self.pd = pd

        if not isinstance(attribute, str):
            print("ERROR: attribute must be a string, check the name on your textfile")

        self.crs = CRS(crs)
        self.attribute = attribute
        self.nodatavalue = nodatavalue

        # Standardize the dataframe
        self.pd.dropna(how='any', inplace=True, axis=0)
        # Create the dictionary with new label names and then rename for standardization
        new_names = {self.pd.columns[0]: 'x', self.pd.columns[1]: 'y', self.pd.columns[2]: self.attribute}
        self.pd = self.pd.rename(columns=new_names)

        # Create geodataframe from the dataframe
        gdf = geopandas.GeoDataFrame(self.pd, geometry=geopandas.points_from_xy(self.pd.x, self.pd.y))
        gdf.crs = self.crs
        self.gdf = gdf
        self.x = gdf.geometry.x.values
        self.y = gdf.geometry.y.values
        self.z = gdf[attribute].values

        if np.isfinite(ulc[0]) and np.isfinite(lrc[0]):
            self.xmax = lrc[0]
            self.xmin = ulc[0]
            self.ymax = ulc[1]
            self.ymin = lrc[1]
        else:
            self.xmax = self.gdf.geometry.x.max()
            self.xmin = self.gdf.geometry.x.min()
            self.ymax = self.gdf.geometry.y.max()
            self.ymin = self.gdf.geometry.y.min()

        self.extent = (self.xmin, self.xmax, self.ymin, self.ymax)

        if np.isfinite(res):
            self.res = res
        else:
            # if res not passed, then res will be the distance between xmin and xmax / 1000
            self.res = (self.xmax - self.xmin) / 1000

        self.ncol = int(np.ceil((self.xmax - self.xmin) / self.res))  # delx
        self.nrow = int(np.ceil((self.ymax - self.ymin) / self.res))  # dely

    def points_to_grid(self):
        """ Creates a grid of new points in the desired resolution to be interpolated
        :return: array of size nrow, ncol

        http://chris35wills.github.io/gridding_data/
        """
        hrange = ((self.ymin, self.ymax),
                  (self.xmin, self.xmax))  # any points outside of this will be condisdered outliers and not used

        zi, yi, xi = np.histogram2d(self.y, self.x, bins=(int(self.nrow), int(self.ncol)), weights=self.z, normed=False,
                                    range=hrange)
        counts, _, _ = np.histogram2d(self.y, self.x, bins=(int(self.nrow), int(self.ncol)), range=hrange)
        np.seterr(divide='ignore', invalid='ignore')  # ignores errors if dividing by zero
        zi = np.divide(zi, counts)
        np.seterr(divide=None, invalid=None)  # set it back now
        zi = np.ma.masked_invalid(zi)
        array = np.flipud(np.array(zi))  # flips each column upside down

        return array

    def norm_array(self, method='linear'):
        """ Normalizes the raw data in equally sparsed points depending on the selected resolution
        :return: interpolated and normalized array with selected resolution

        https://github.com/rosskush/skspatial
        """
        array = self.points_to_grid()
        x = np.arange(0, self.ncol)  # creates 1d array with values [0, ncol[
        y = np.arange(0, self.nrow)

        # mask invalid values
        array = np.ma.masked_invalid(array)  # all invalid values are masked (ex.: np.inf or np.nan)
        xx, yy = np.meshgrid(x, y)  # creates a grid of values with (x,y) based on the x and y provided

        # get only the valid values
        x1 = xx[~array.mask]  # takes only unmasked points
        y1 = yy[~array.mask]
        newarr = array[~array.mask]

        out_array = interpolate.griddata((x1, y1), newarr.ravel(), (xx, yy), method=method, fill_value=self.nodatavalue)

        return out_array

    def random_raster(self, raster_file, save_ascii=True, **kwargs):
        """ Creates a raster of randomly generated values
        :kwarg minmax: tuple of floats, (zmin, zmax) min and max ranges for random values
        :return: array of random values within a range of the same size and chape as the original
        """

        if kwargs['minmax'] is None:
            zmin, zmax = self.z.min(), self.z.max()
        else:
            zmin, zmax = kwargs['minmax']

        array = np.random.uniform(low=zmin, high=zmax, size=(self.nrow, self.ncol))

        if '.' not in raster_file[-4:]:
            raster_file += '.tif'

        self.transform = rio.transform.from_origin(self.xmin, self.ymax, self.res, self.res)

        new_dataset = rio.open(raster_file, 'w', driver='GTiff',
                               height=array.shape[0], width=array.shape[1], count=1, dtype=array.dtype,
                               crs=self.crs, transform=self.transform, nodata=self.nodatavalue)
        print('The array has size: ', np.shape(array))

        new_dataset.write(array, 1)
        new_dataset.close()

        if save_ascii:
            map_asc = str(Path(raster_file[0:-4] + '.asc'))
            gdal.Translate(map_asc, raster_file, format='AAIGrid')

        return new_dataset

    def plain_raster(self, shapefile, raster_file, res):
        """ Converts shapefile(.shp) to rasters(.tif) without normalizing
        :param shapefile: string, filename with path of the input shapefile (*.shp)
        :param raster_file: stirng, filename with path of the output raster (*.tif)
        :param res: float, resolution of the cell
        :return: saves the raster in the default directory
        """
        if '.' not in shapefile[-4:]:
            shapefile += '.shp'

        if '.' not in raster_file[-4:]:
            raster_file += '.tif'
        source_ds = ogr.Open(shapefile)
        source_layer = source_ds.GetLayer()
        x_min, x_max, y_min, y_max = source_layer.GetExtent()

        # Create Target - TIFF
        cols = int((x_max - x_min) / res)
        rows = int((y_max - y_min) / res)
        _raster = gdal.GetDriverByName('GTiff').Create(raster_file, cols, rows, 1, gdal.GDT_Float32)
        _raster.SetGeoTransform((x_min, res, 0, y_max, 0, res))
        _band = _raster.GetRasterBand(1)
        _band.SetNoDataValue(self.nodatavalue)

        # Rasterize
        gdal.RasterizeLayer(_raster, [1], source_layer, options=['ATTRIBUTE=' + self.attribute])

    def array2raster(self, array, raster_file, save_ascii=True):
        """ Saves a raster using interpolation
        :param raster_file: string, path to save the rasterfile
        :param save_ascii: boolean, true to save also an ascii raster
        :return: saves the raster with the selected filename
        """
        if '.' not in raster_file[-4:]:
            raster_file += '.tif'

        self.transform = rio.transform.from_origin(self.xmin, self.ymax, self.res, self.res)
        new_dataset = rio.open(raster_file, 'w', driver='GTiff',
                               height=array.shape[0], width=array.shape[1], count=1, dtype=array.dtype,
                               crs=self.crs, transform=self.transform, nodata=self.nodatavalue)
        print(np.shape(array))
        new_dataset.write(array, 1)
        new_dataset.close()

        if save_ascii:
            map_asc = str(Path(raster_file[0:-4] + '.asc'))
            gdal.Translate(map_asc, raster_file, format='AAIGrid')

        return new_dataset

    def create_polygon(self, shape_polygon, alpha=np.nan):
        """ Creates a polygon surrounding a cloud of shapepoints
        :param shape_polygon: string, path to save the shapefile
        :param alpha: float, excentricity of the alphashape (polygon) to be created
        :return: saves the polygon (*.shp) with the selected filename
        """
        if np.isfinite(alpha):
            try:
                polygon = alphashape.alphashape(self.gdf, alpha)
                polygon.crs = self.crs
                polygon.to_file(shape_polygon)
                print('Polygon *.shp saved successfully.')
            except FileNotFoundError as e:
                print(e)
        else:
            try:
                polygon = alphashape.alphashape(self.gdf)
            except FileNotFoundError as e:
                print(e)
            else:
                polygon.crs = self.crs
                polygon.to_file(shape_polygon)
                print('Polygon *.shp saved successfully.')


class PreProCategorization:
    def __init__(self, raster):
        """ Clips a raster based on the given polygon
            :param raster: string, path of the raster to be categorized
        """
        self.raster = raster

        with rio.open(self.raster) as src:
            raster_np = src.read(1, masked=True)
            self.nodatavalue = src.nodata  # storing nodatavalue of raster
            self.meta = src.meta.copy()
        self.array = raster_np

    def nb_classes(self, n_classes):
        """ Generates class bins based on the Natural Breaks method
            :param n_classes: integer, number of classes
            :return: list, optimized bins
        """
        # Classification based on Natural Breaks
        array_values = self.array[~self.array.mask].ravel()
        breaks = mc.NaturalBreaks(array_values, k=n_classes)
        print('The upper bound of the classes are:', breaks.bins)  # bins being (], (], (]....(] always including the right
        print('Number of counts for each class, respectively:', breaks.counts)
        print('max: ', array_values.max(), 'min: ', array_values.min())
        return breaks.bins

    def categorize_raster(self, class_bins, map_out, save_ascii=True):
        """ Classifies the raster according to the classification bins
        :param project_dir: path of the project directory
        :param class_bins: list of floats,
        :return: saves the classified raster in the chosen directory
        """
        # Classify the original image array (digitize makes nodatavalues take the class 0)
        raster_fi = np.ma.filled(self.array, fill_value=-np.inf)
        raster_class = np.digitize(raster_fi, class_bins, right=True)  # bins[i-1] < array <= bins[i]

        # Assigns nodatavalues back to array
        raster_ma = np.ma.masked_where(raster_class == 0,
                                       raster_class,
                                       copy=True)

        # Fill nodatavalues into array
        raster_ma_fi = np.ma.filled(raster_ma, fill_value=self.nodatavalue)
        # raster_ma_fi = np.ma.filled(raster_class, fill_value=self.nodatavalue)

        if raster_ma_fi.min() == self.nodatavalue or type(raster_ma_fi) != np.ma.MaskedArray:
            with rio.open(map_out, 'w', **self.meta) as outf:
                outf.write(raster_ma_fi.astype(rio.float64), 1)
        else:
            raise TypeError("Error filling NoDataValue to raster file")

        if save_ascii:
            map_asc = str(Path(map_out[0:-4] + '.asc'))
            gdal.Translate(map_asc, map_out, format='AAIGrid')
