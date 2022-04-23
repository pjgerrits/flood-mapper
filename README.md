# flood-mapper

Detect flood extents on Sentinel-1 satellite imagery using the [recommended method from United Nations UN-SPIDER Knowledge Portal](https://un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping/step-by-step#Step%202:%20Time%20frame%20and%20sensor%20parameters%20selection
).

## Installation

`pip install flood-mapper`


## Usage

```python
import ee
from flood_mapper import derive_flood_extents

ee.Initialize()
ee.Authenticate()

# Define a start and end date between to select imagery before the flooding event
before_start = '2020-10-01'
before_end = '2020-10-15'

# Define a start and end date between to select imagery after the flooding event
after_start = '2020-11-04'
after_end = '2020-11-15'

# Define a geographic region where the flooding occurred.
region = ee.Geometry.Polygon([[[-85.93, 16.08],
                               [-85.93, 15.69],
                               [-85.40, 15.69],
                               [-85.40, 16.08]]])

# Change the export flag to 'False' if you do not wish to export the results to Google Drive
detected_flood_vector, detected_flood_raster, before_imagery, after_imagery = derive_flood_extents(region,
                                                                                                   before_start,
                                                                                                   before_end,
                                                                                                   after_start,
                                                                                                   after_end,
                                                                                                   export=True,
                                                                                                   export_filename='my_filename')

```