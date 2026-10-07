"""Exact existing ordinary fixture constructors; no original query."""

from copy import deepcopy

def block(grid,r,c,size,color):
    for rr in range(r,r+size):
        for cc in range(c,c+size):grid[rr][cc]=color

def pair(n=0,a=1,b=2,pitch=3):
    grid=[[0]*(25+n)for _ in range(25+n)]
    for r,c,color in ((1,1,2),(1,1+a+1,3),(1+a+1,1,4),(1+a+1,1+a+1,5)):
        block(grid,r,c,a,color)
    block(grid,11+n,12,b,2);block(grid,11+n,12+pitch,b,3)
    out=deepcopy(grid);block(out,11+n+pitch,12,b,4);block(out,11+n+pitch,12+pitch,b,5)
    return {'input':grid,'output':out}

def symmetric_pair():
    grid=[[0]*25 for _ in range(25)]
    for r,c,color in ((1,1,2),(1,3,2),(3,1,4),(3,3,4)):
        grid[r][c]=color
    block(grid,10,12,2,2);block(grid,10,16,2,2)
    out=deepcopy(grid);block(out,14,12,2,4);block(out,14,16,2,4)
    return {'input':grid,'output':out}

def remap(grid):return [[(v+4)%10 for v in row]for row in grid]

def source_oracle(grid, center, body):
    """Literal independent opposite-tile ownership with an explicit synthetic body."""
    cr, cc = center
    output = [row[:] for row in grid]
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0:
                continue
            for r in range(3):
                for c in range(3):
                    output[cr + 6 * dr + r - 1][cc + 6 * dc + c - 1] = grid[cr - 3 * dr + r - 1][cc - 3 * dc + c - 1]
            output[cr + dr][cc + dc] = grid[cr + 2 * dr][cc + 2 * dc]
    output[cr][cc] = body
    return output

def orbit_change(grid, center, orbit, value):
    output = [row[:] for row in grid]
    cr, cc = center
    for r in range(cr - 4, cr + 5):
        for c in range(cc - 4, cc + 5):
            if tuple(sorted((abs(r - cr), abs(c - cc)), reverse=True)) == orbit:
                output[r][c] = value
    return output

def dense_ornament():
    # Body 1 is sparse but spans every tile. Ornament 4 is both corner and mode.
    g = [[8] * 17 for _ in range(17)]
    values = {(2, 0): 2, (2, 1): 1, (2, 2): 3,
              (3, 0): 4, (3, 1): 4, (3, 2): 4, (3, 3): 4,
              (4, 0): 1, (4, 1): 4, (4, 2): 1, (4, 3): 4, (4, 4): 4}
    for r in range(-4, 5):
        for c in range(-4, 5):
            key = tuple(sorted((abs(r), abs(c)), reverse=True))
            if key in values:
                g[r + 8][c + 8] = values[key]
    return g

def pad(grid, top=2, left=3, bottom=1, right=2):
    width = len(grid[0]) + left + right
    return ([[8] * width for _ in range(top)]
            + [[8] * left + row + [8] * right for row in grid]
            + [[8] * width for _ in range(bottom)])
