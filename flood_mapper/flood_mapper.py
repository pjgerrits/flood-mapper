import ee

ee.Initialize()


def retrieve_image_collection(region, start_date, end_date, polarization="VH", pass_direction="ASCENDING"):

    collection = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filter(ee.Filter.eq('instrumentMode', 'IW'))\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization))\
        .filter(ee.Filter.eq('orbitProperties_pass', pass_direction))\
        .filter(ee.Filter.eq('resolution_meters', 10))\
        .filterDate(start_date, end_date)\
        .filterBounds(region)\
        .select(polarization)

    return collection


def smooth(image, smoothing_radius=50):
    # Apply reduce the radar speckle by smoothing
    smoothed_image = image.focal_mean(smoothing_radius, 'circle', 'meters')
    return smoothed_image


def mask_permanent_water(image):

    surface_water = ee.Image('JRC/GSW1_0/GlobalSurfaceWater').select('seasonality')
    surface_water_mask = surface_water.gte(10).updateMask(surface_water.gte(10))

    # Flooded layer where perennial water bodies(water > 10 mo / yr) is assigned a 0 value
    flooded_mask = image.where(surface_water_mask, 0)

    # Final flooded area
    flooded_area = image.updateMask(flooded_mask)

    return flooded_area


def reduce_noise(image):
    # Compute connectivity of pixels to eliminate those connected to 8 or fewer neighbours
    # This operation reduces noise of the flood extent product
    connections = image.connectedPixelCount()
    flooded_area_reduced_noise = image.updateMask(connections.gte(8))

    return flooded_area_reduced_noise


def mask_slopes(image):

    dem = ee.Image('WWF/HydroSHEDS/03VFDEM')
    terrain = ee.Algorithms.Terrain(dem)
    slope = terrain.select('slope')
    slopes_masked = image.updateMask(slope.lt(5))

    return slopes_masked


# def geometry_checker(geometry):
#     """
#     Checks to see if user AOI is a valid Earth Engine geometry
#     :return:
#     """
#
#     if # geomety is valid
#         return True
#
#     else:
#         print('Input geometry is not a valid geomstry.')
#         return False


def flood_mapper_func(aoi, before_start_date, before_end_date, after_start_date, after_end_date, difference_threshold=1.25):

    # TODO add geometry checker function

    # Select images by predefined dates
    before_flood_img_col = retrieve_image_collection(aoi, before_start_date, before_end_date)
    after_flood_img_col = retrieve_image_collection(aoi, after_start_date, after_end_date)

    # Create a mosaic of selected tiles and clip to study area
    before_mosaic = before_flood_img_col.mosaic().clip(aoi)
    after_mosaic = after_flood_img_col.mosaic().clip(aoi)

    before_filtered = smooth(before_mosaic)
    after_filtered = smooth(after_mosaic)

    # Calculate the difference between the before and after images
    difference = after_filtered.divide(before_filtered)

    # Apply the predefined difference - threshold and create the flood extent mask
    difference_binary = difference.gt(difference_threshold)
    difference_binary_masked = mask_permanent_water(difference_binary)
    difference_binary_masked_reduced_noise = reduce_noise(difference_binary_masked)
    flood_rasters = mask_slopes(difference_binary_masked_reduced_noise)

    # Export the extent of detected flood in vector format
    flood_vectors = flood_rasters.reduceToVectors(scale=10,
                                                  geometryType='polygon',
                                                  geometry=aoi,
                                                  eightConnected=False,
                                                  bestEffort=True,
                                                  tileScale=2)

    s1_imagery = after_filtered

    return flood_vectors, flood_rasters, s1_imagery


if __name__ == "__main__":

    before_start = '2020-10-01'
    before_end = '2020-10-15'

    after_start = '2020-11-04'
    after_end = '2020-11-15'

    region = ee.Geometry.Polygon([[[-85.93, 16.08],
                                [-85.93, 15.69],
                                [-85.40, 15.69],
                                [-85.40, 16.08]]])

    detected_flood_vector, detected_flood_raster, imagery = flood_mapper_func(region,
                                                                         before_start,
                                                                         before_end,
                                                                         after_start,
                                                                         after_end)

    # print(detected_flood_vector)
    # print(detected_flood_raster.getInfo())
    # print(imagery)