import ee
from flood_mapper import derive_flood_extents

before_start = '2020-10-01'
before_end = '2020-10-15'

after_start = '2020-11-04'
after_end = '2020-11-15'

region = ee.Geometry.Polygon([[[-85.93, 16.08],
                               [-85.93, 15.69],
                               [-85.40, 15.69],
                               [-85.40, 16.08]]])

detected_flood_vector, detected_flood_raster, imagery = derive_flood_extents(region,
                                                                             before_start,
                                                                             before_end,
                                                                             after_start,
                                                                             after_end)
