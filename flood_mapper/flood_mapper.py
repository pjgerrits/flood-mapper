import ee
import time

ee.Initialize()


def _check_task_completed(task_id):
    """
    Returns True if a task export completes successfully, else returns false.

    Inputs:
        task_id (str): Google Earth Engine task id

    Returns:
        boolean

    """
    status = ee.data.getTaskStatus(task_id)[0]
    if status['state'] in (ee.batch.Task.State.CANCELLED,
                           ee.batch.Task.State.FAILED):
        if 'error_message' in status:
            print(status['error_message'])
        return True
    elif status['state'] == ee.batch.Task.State.COMPLETED:
        return True
    return False


def wait_for_tasks(task_ids=[], timeout=3600):
    """
    Wait for tasks to complete, fail, or timeout
    Waits for all active tasks if task_ids is not provided
    Note: Tasks will not be canceled after timeout, and
    may continue to run.

    Inputs:
        task_ids (list):
        timeout (int):

    Returns:
        None
    """
    start = time.time()
    elapsed = 0
    while elapsed < timeout or timeout == 0:
        elapsed = time.time() - start
        finished = [_check_task_completed(task) for task in task_ids]
        if all(finished):
            print(f'Tasks {task_ids} completed after {elapsed}s')
            return True
        time.sleep(5)
    print(f'Stopped waiting for {len(task_ids)} tasks after {timeout} seconds')
    return False


def export_flood_data(flooded_area_vector, flooded_area_raster, image_after_flood, region):
    """
    Exports the results of derive_flood_extents function to Google Drive.

    Inputs:
        flooded_area_vector (ee.FeatureCollection): Detected flood extents as vector geometries.
        flooded_area_raster (ee.Image): Detected flood extents as a binary raster.
        image_after_flood (ee.Image): The 'after' Sentinel-1 image containing view of the flood waters.
        region (ee.Geometry.Polygon): Geographic extent of analysis area.

    Returns:
        None
    """

    print('Exporting detected flood extents to your Google Drive. Please wait...')

    s1_task = ee.batch.Export.image.toDrive(image=image_after_flood,
                                            description='s1_flooded_scene',
                                            scale=30,
                                            region=region,
                                            fileNamePrefix='s1_flooded_scene',
                                            crs='EPSG:4326',
                                            fileFormat='GeoTIFF')

    raster_task = ee.batch.Export.image.toDrive(image=flooded_area_raster,
                                                description='flood_extents',
                                                scale=30,
                                                region=region,
                                                fileNamePrefix='flood_extents',
                                                crs='EPSG:4326',
                                                fileFormat='GeoTIFF')

    vector_task = ee.batch.Export.table.toDrive(collection=flooded_area_vector,
                                                description='flood_extents_vector',
                                                fileFormat='shp',
                                                fileNamePrefix='flood_extents_vector')

    s1_task.start()
    raster_task.start()
    vector_task.start()

    print('Exporting flooded Sentinel-1 scene: Task id ', s1_task.id)
    print('Exporting flood extent geotiff: Task id ', raster_task.id)
    print('Exporting flood extent shapefile:  Task id ', vector_task.id)

    wait_for_tasks([s1_task.id, raster_task.id, vector_task.id])


def retrieve_image_collection(search_region, start_date, end_date, polarization="VH", pass_direction="ASCENDING"):
    """

    Inputs:
        search_region (ee.Geometry.Polygon): Geographic extent of image search.
        start_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        end_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        polarization (str): Synthetic aperture radar polarization mode, e.g., 'VH' or 'VV'. VH is mostly is the preferred
            polarization for flood mapping.
        pass_direction (str): Synthetic aperture radar pass direction, either 'ASCENDING' or 'DESCENDING'.

    Returns:
        collection (ee.ImageCollection): Sentinel-1 images matching the search criteria.
    """

    collection = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filter(ee.Filter.eq('instrumentMode', 'IW'))\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization))\
        .filter(ee.Filter.eq('orbitProperties_pass', pass_direction))\
        .filter(ee.Filter.eq('resolution_meters', 10))\
        .filterDate(start_date, end_date)\
        .filterBounds(search_region)\
        .select(polarization)

    return collection


def smooth(image, smoothing_radius=50):
    """
    Reduce the radar speckle by smoothing.

    Inputs:
        image (ee.Image): Input image.
        smoothing_radius (int): The radius of the kernel to use for focal mean smoothing.

    Returns:
        smoothed_image (ee.Image): The resulting image after smoothing is applied.
    """

    smoothed_image = image.focal_mean(smoothing_radius, 'circle', 'meters')

    return smoothed_image


def mask_permanent_water(image):
    """
    Query the JRC Global Surface Water Mapping Layers, v1.3, to determine where perennial water bodies
    (water > 10 months/yr), and mask these areas.

    Inputs:
        image (ee.Image): Input image.

    Returns:
        masked_image (ee.Image): The resulting image after surface water masking is applied.
    """

    surface_water = ee.Image('JRC/GSW1_3/GlobalSurfaceWater').select('seasonality')
    surface_water_mask = surface_water.gte(10).updateMask(surface_water.gte(10))

    # Flooded layer where perennial water bodies(water > 10 mo / yr) is assigned a 0 value
    where_surface_water = image.where(surface_water_mask, 0)

    masked_image = image.updateMask(where_surface_water)

    return masked_image


def reduce_noise(image):
    """
    Compute connectivity of pixels to eliminate those connected to 8 or fewer neighbours. This operation reduces noise
    of the flood extent product.

    Inputs:
        image (ee.Image): A binary image.

    Returns:
        reduced_noise_image (ee.Image): The resulting image after noise reduction is applied.
    """

    connections = image.connectedPixelCount()
    reduced_noise_image = image.updateMask(connections.gte(8))

    return reduced_noise_image


def mask_slopes(image):
    """
    Mask out areas with more than 5 percent slope using a Digital Elevation Model.

    Inputs:
        image (ee.Image): Input image.
    Returns:
         slopes_masked (ee.Image): The resulting image after slope masking is applied.
    """

    dem = ee.Image('WWF/HydroSHEDS/03VFDEM')
    terrain = ee.Algorithms.Terrain(dem)
    slope = terrain.select('slope')
    slopes_masked = image.updateMask(slope.lt(5))

    return slopes_masked


def derive_flood_extents(aoi, before_start_date, before_end_date, after_start_date, after_end_date,
                         difference_threshold=1.25, export=False):
    """
    Set start and end dates of a period BEFORE and AFTER a flood. These periods need to be long enough for Sentinel-1 to
    acquire an image.

    Inputs:
        aoi (ee.Geometry.Polygon): Geographic extent of analysis area.
        before_start_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        before_end_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        after_start_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        after_end_date (str): Date in format yyyy-mm-dd, e.g., '2020-10-01'.
        difference_threshold (float): Threshold to be applied on the differenced image (after flood - before flood). It
            has been chosen by trial and error. In case your flood extent result shows many false-positive or negative
            signals, consider changing it.

    Returns:
        flood_vectors (ee.FeatureCollection): Detected flood extents as vector geometries.
        flood_rasters (ee.Image): Detected flood extents as a binary raster.
        flooded_image (ee.Image): The 'after' Sentinel-1 image containing view of the flood waters.
    """

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

    if export:
        export_flood_data(flood_vectors, flood_rasters, after_filtered, aoi)

    return flood_vectors, flood_rasters, after_filtered
