## vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
## Copyright (c) 2017 Marko Mahnič. All rights reserved.
## Licensed under the MIT License. See LICENSE file in the project root for full license information.

import math

# Calculate the widths of the columns.
# The number if items in each column is in @p itemCounts.
# The width of a note is @p itemUnits out of @p units. Empty columns are @p emptyUnits wide.
def distributeItems( itemCounts, units=12, itemUnits=2, emptyUnits=1 ):
    if len(itemCounts) == 0:
        return []
    if len(itemCounts) * emptyUnits > units:
        raise Exception( "Too many columns" )

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
    sizes = [ max(int(math.ceil(s * factor)), itemUnits) if s > emptyUnits else s for s in sizes ]

    overhead = sum(sizes) - units
    if overhead > 0:
        items = [ [s,ic] for ic,s in enumerate(sizes) if s > emptyUnits ]
        items = sorted( items, key=lambda x: (-x[0], x[1]) ) + [ [0, -1] ]

        # reduce odd sizes
        for i in xrange(len(items) - 1):
            if items[i][0] % 2 == 1 and items[i][0] > itemUnits:
                items[i][0] -= 1
                overhead -= 1
            if overhead == 0:
                break

        # reduce sizes by 2
        if overhead > 1:
            for i in xrange(len(items) - 1):
                if items[i][0] > items[i+1][0] and items[i][0] > itemUnits:
                    items[i][0] -= 2
                    overhead -= 2
                if overhead < 2:
                    break

        while overhead > 0:
            for i in xrange(overhead):
                if items[i][0] > emptyUnits:
                    items[i][0] -= 1
                    overhead -= 1
                if overhead < 1:
                    break

        for (s,ic) in items:
            if ic >= 0:
                sizes[ic] = s

    return sizes

