"""四欄のmask・成分数・二配色を反復へ結ぶ新しい組合せ。"""
from __future__ import annotations
from collections import Counter
from .既存物体特徴 import color_component_dicts_for_grid

def valid_grid(grid):
    return (isinstance(grid,list) and 1<=len(grid)<=30
            and isinstance(grid[0],list) and 1<=len(grid[0])<=30
            and all(isinstance(row,list) and len(row)==len(grid[0])
                    and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def parse_input(grid):
    if not valid_grid(grid):return None,{'failure':'invalid_grid'}
    height,width=len(grid),len(grid[0]);raw=[]
    for axis,extent in [('rows',height),('columns',width)]:
        for colour in sorted({v for row in grid for v in row}):
            positions=([i for i,row in enumerate(grid)if all(v==colour for v in row)]if axis=='rows'
                       else[j for j in range(width)if all(grid[i][j]==colour for i in range(height))])
            if (len(positions)!=3 or positions[0]==0 or positions[-1]==extent-1
                    or any(b-a<=1 for a,b in zip(positions,positions[1:]))):continue
            stops=[-1,*positions,extent]
            raw.append({'axis':axis,'separator_colour':colour,'separator_positions':positions,
                        'intervals':[[a+1,b]for a,b in zip(stops,stops[1:])]})
    base={'input_shape':[height,width],'raw_layout_candidates':raw}
    if len(raw)!=1:return None,{**base,'failure':'raw_layout_not_unique'}
    layout=raw[0];axis=layout['axis'];intervals=layout['intervals']
    fields=([grid[a:b]for a,b in intervals]if axis=='rows'
            else[[row[a:b]for row in grid]for a,b in intervals])
    palettes=[set(v for row in field for v in row)for field in fields]
    shapes=[[len(field),len(field[0])]for field in fields]
    base.update(field_shapes=shapes,field_palettes=[sorted(s)for s in palettes])
    if len(palettes[0])!=2 or len(palettes[1])!=2:return None,{**base,'failure':'mask_count_fields_not_binary'}
    common=palettes[0]&palettes[1]
    if len(common)!=1:return None,{**base,'failure':'shared_blank_not_unique'}
    if len(palettes[2])!=1 or len(palettes[3])!=1:return None,{**base,'failure':'palette_field_not_uniform'}
    blank=next(iter(common));mask_colour=next(iter(palettes[0]-{blank}));count_colour=next(iter(palettes[1]-{blank}))
    paint,fill=next(iter(palettes[2])),next(iter(palettes[3]))
    mask_cells={(r,c)for r,row in enumerate(fields[0])for c,v in enumerate(row)if v==mask_colour}
    count_cells={(r,c)for r,row in enumerate(fields[1])for c,v in enumerate(row)if v==count_colour}
    if not mask_cells or not count_cells:return None,{**base,'failure':'empty_mask_or_count'}
    r0=min(r for r,c in mask_cells);r1=max(r for r,c in mask_cells);c0=min(c for r,c in mask_cells);c1=max(c for r,c in mask_cells)
    mask=[[fields[0][r][c]==mask_colour for c in range(c0,c1+1)]for r in range(r0,r1+1)]
    components=color_component_dicts_for_grid(fields[1],count_colour,include_diagonal=False)
    covered=set();records=[]
    for component in components:
        cells=set(component['cells'])
        if not cells or cells&covered or not cells.issubset(count_cells):return None,{**base,'failure':'count_component_ownership_failed'}
        covered.update(cells);records.append({'cells':[list(p)for p in sorted(cells)],'size':len(cells),'bbox':list(component['bbox'])})
    if covered!=count_cells or not records:return None,{**base,'failure':'count_pixels_not_fully_owned'}
    separator_cells=3*(width if axis=='rows'else height)
    field_cells=sum(h*w for h,w in shapes)
    if separator_cells+field_cells!=height*width:return None,{**base,'failure':'input_partition_incomplete'}
    return {'axis':axis,'blank':blank,'mask':mask,'paint':paint,'fill':fill,'count':len(records)}, {
        **base,'blank':blank,'mask_colour':mask_colour,'count_colour':count_colour,'paint_colour':paint,'fill_colour':fill,
        'mask_bbox':[r0,c0,r1,c1],'mask_shape':[r1-r0+1,c1-c0+1],'mask_active_cells':len(mask_cells),
        'count_components':records,'count_pixels':len(count_cells),'repeat_count':len(records),
        'separator_cells':separator_cells,'field_cells':field_cells}

def render(grid):
    parsed,record=parse_input(grid)
    if parsed is None:return None,record
    axis=parsed['axis'];mask=parsed['mask'];mh,mw=len(mask),len(mask[0]);n=parsed['count']
    height,width=(n*mh+n-1,mw)if axis=='rows'else(mh,n*mw+n-1)
    base={**record,'output_shape':[height,width]}
    if not(1<=height<=30 and 1<=width<=30):return None,{**base,'failure':'output_outside_arc'}
    output=[];copy_cells=gap_cells=active_cells=0;colours=Counter()
    for row in range(height):
        values=[]
        for col in range(width):
            position=row if axis=='rows'else col
            index,offset=divmod(position,(mh if axis=='rows'else mw)+1)
            gap=offset==(mh if axis=='rows'else mw)
            if gap:
                value=parsed['fill'];gap_cells+=1
            else:
                mr,mc=(offset,col)if axis=='rows'else(row,offset)
                active=mask[mr][mc];value=parsed['paint']if active else parsed['fill']
                active_cells+=active;copy_cells+=1
            values.append(value);colours[value]+=1
        output.append(values)
    expected_copy=n*mh*mw;expected_gap=(n-1)*(mw if axis=='rows'else mh)
    if (copy_cells!=expected_copy or gap_cells!=expected_gap or copy_cells+gap_cells!=height*width
            or active_cells!=n*record['mask_active_cells']):return None,{**base,'failure':'output_ownership_failed'}
    return output,{**base,'copy_cells':copy_cells,'gap_cells':gap_cells,'paint_owned_cells':active_cells,
                   'fill_owned_cells':height*width-active_cells,'output_colour_counts':[[v,c]for v,c in sorted(colours.items())]}

def fit_teachers(train):
    if not isinstance(train,list)or len(train)<2:return None,{'failure':'too_few_teachers'}
    if any(not isinstance(p,dict)or not valid_grid(p.get('input'))or not valid_grid(p.get('output'))for p in train):
        return None,{'failure':'invalid_teachers'}
    keys=[tuple(map(tuple,p['input']))for p in train]
    if len(set(keys))!=len(keys):return None,{'failure':'duplicate_teacher_inputs'}
    records=[]
    for pair in train:
        output,record=render(pair['input']);records.append({'exact':output==pair['output'],'record':record})
    if not all(r['exact']for r in records):return None,{'failure':'teacher_mismatch','teacher_records':records}
    return {'renderer':'four_field_repeat'},{'teacher_records':records}

class 四欄反復教材:
    def __init__(self, 教師群):
        model, record = fit_teachers(教師群)
        self.適合 = model is not None
        # NEW reconstruction only after the unchanged old fitter completed all
        # teacher comparisons and returned its ordinary teacher_mismatch.
        rows = record.get('teacher_records', [])
        if (self.適合 or record.get('failure') != 'teacher_mismatch'
                or record.get('complete', True) is not True
                or not isinstance(rows, list) or len(rows) != len(教師群)
                or any(not isinstance(row, dict) or type(row.get('exact')) is not bool
                       or not isinstance(row.get('record'), dict)
                       or row['record'].get('complete', True) is not True for row in rows)
                or not any(row['exact'] is False for row in rows)):
            return
        from .標識二領域再構成 import fit_teachers as fit_regions
        actions, _ = fit_regions(教師群)
        if actions:
            self.領域作用群 = actions

    def 候補(self, 格子, _policy):
        if self.適合:
            return render(格子)
        if hasattr(self, '領域作用群'):
            from .標識二領域再構成 import predict
            return predict(格子, self.領域作用群)
        return None, {"failure": "全教師を再現する四欄反復なし"}

    def 記録(self):
        record = {"全教師の四欄再現": self.適合}
        if hasattr(self, '領域作用群'):
            record['NEW標識二領域作用群'] = [list(action) for action in self.領域作用群]
        return record
