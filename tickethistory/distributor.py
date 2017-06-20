## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

# Calculate the widths of the columns.
# The number if items in each column is in @p itemCounts.
# The width of a note is @p itemUnits out of @p units. Empty columns are @p emptyUnits wide.
def distributeItems( itemCounts, units=12, itemUnits=2, emptyUnits=1 ):
    if len(itemCounts) == 0:
        return []

    # empty table
    if sum( itemCounts ) == 0:
        percolumn = units / len(itemCounts)
        sizes = [percolumn for c in itemCounts]
        if sum(sizes) < 12:
            sizes[0] += 12 - sum(sizes)
        return sizes

    sizes = [max(c*2, emptyUnits) for c in itemCounts]

    # scale the sizes by a factor to reach the total number of units
    total = 12 - sum([s for s in sizes if s == emptyUnits])
    allocated = sum([s for s in sizes if s > emptyUnits])
    factor = float(total) / allocated
    sizes = [ max(int(s * factor + 0.5), itemUnits) if s > emptyUnits else s for s in sizes ]

    overhead = sum(sizes) - units
    for ic in xrange(overhead):
        sizes[ic] -= 1

    return sizes

