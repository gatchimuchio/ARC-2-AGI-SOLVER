"""Conservative background-padding input view around unchanged strict Grammar.

The fitted programs remain strict-teacher programs. The new boundary semantics
is an explicit fixed prior and does not add a projected-output fitter.
"""
from copy import deepcopy


def render_window(grid, model, grammar, crop_grid):
    if not grammar.valid_grid(grid):
        return None, {'failure': 'invalid_original_arc_grid'}
    bg, shape, anchor, corner, entries = model
    if grammar.mode(grid) != bg:
        return None, {'failure': 'original_background_mismatch_or_tie'}
    h, w = len(grid), len(grid[0])
    gh, gw = shape
    keys = set(dict(entries))
    tokens = [(r, c) for r, row in enumerate(grid)
              for c, value in enumerate(row) if value in keys]
    top = min([0] + [r-anchor[0] for r,c in tokens])
    left = min([0] + [c-anchor[1] for r,c in tokens])
    bottom = max([h] + [r-anchor[0]+gh for r,c in tokens])
    right = max([w] + [c-anchor[1]+gw for r,c in tokens])
    ph, pw = bottom-top, right-left
    view = {'original_shape': [h,w], 'all_key_token_count': len(tokens),
            'support_envelope': [top,left,bottom,right],
            'padded_shape': [ph,pw], 'translation': [-top,-left],
            'conservative_all_keys_include_labels': True}
    if not (1 <= ph <= 30 and 1 <= pw <= 30):
        return None, {**view, 'failure': 'padded_domain_outside_arc_bounds'}
    padded = [[bg]*pw for _ in range(ph)]
    for r,row in enumerate(grid):
        padded[r-top][-left:-left+w] = list(row)
    output, detail = grammar.render(padded, model)
    record = {**view, 'strict_renderer_record': deepcopy(detail)}
    if output is None:
        return None, {**record, 'failure': 'strict_renderer_HOLD'}
    cropped = crop_grid(output, (-top,-left,h-1-top,w-1-left))
    if not grammar.valid_grid(cropped):
        return None, {**record, 'failure': 'invalid_cropped_arc_output'}
    return cropped, record


def consensus_window(grid, models, grammar, crop_grid):
    returns = [render_window(grid, model, grammar, crop_grid) for model in models]
    record = {'returns': deepcopy(returns), 'all_retained_models_evaluated': len(returns)}
    if not returns or any(output is None for output,_ in returns):
        return None, {**record, 'failure': 'one_or_more_retained_models_failed'}
    if any(output != returns[0][0] for output,_ in returns[1:]):
        return None, {**record, 'failure': 'retained_models_disagree'}
    return returns[0][0], record
