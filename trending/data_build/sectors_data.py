from data_build import data_build

# 9 sectors for the SPX
sectors = ["XLU", "XLV", "XLY", "XLK", "XLP", "XLI", "XLF", "XLB", "XLE"]

# ticker = '^GSPC'
source = 'yahoo'
date_start = '1999-01-01'
# symbol = 'SPX'
date_end = '2019-01-11'

for sector in sectors:
    data_build.main(sector, source, date_start, date_end, sector)