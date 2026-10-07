"""Whole-scaffold ownership at frozen095's complete zero-role boundary only.

The frozen parser bytecode is reused with an isolated region-view binding.
Cue validation happens before extending perimeter ownership to its C4 scaffold;
only the parser's already validated cue/source roles consume those perimeters.
"""
from types import FunctionType

from . import 関係枠命令配置 as frozen
from 接続.ARC2.既存枠計数 import color_components

strict = frozen.strict
MODELS = frozen.MODELS
fit = frozen.fit
act = frozen.act
D4 = frozen.D4


def scaffold_regions(panel, frame):
    regions = frozen.framed_regions(panel, frame)
    scaffolds = color_components(panel, frame)
    return [
        {**region, 'perimeter': set().union(*(
            component['cells'] for component in scaffolds
            if component['cells'] & region['perimeter']
        ))}
        for region in regions
    ]


def _bind(function, **bindings):
    """Reuse unchanged code with local dependencies; never mutate frozen globals."""
    return FunctionType(function.__code__, {**function.__globals__, **bindings},
                        function.__name__, function.__defaults__, function.__closure__)


relational_parse = _bind(frozen.relational_parse, framed_regions=scaffold_regions)
_scaffold_render = _bind(frozen.render, relational_parse=relational_parse)


def render(grid, model):
    output, record = frozen.render(grid, model)
    if not (
        output is None
        and record.get('complete') is True
        and record.get('roles') == 0
        and record.get('failure') == 'no_complete_relational_role'
        and any(entry.get('failure') == 'unowned_frame_cells'
                for probe in record['view_probes']
                for entry in probe.get('background_returns', ()))
    ):
        return output, record
    output, scaffold_record = _scaffold_render(grid, model)
    scaffold_record.update(input_view='whole_frame_scaffold', frozen095_record=record)
    return output, scaffold_record


consensus = _bind(frozen.consensus, render=render)
