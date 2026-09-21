"""The localization adapter must preserve Dear ImGui's ## versus ### semantics."""
import ast
from pathlib import Path

def label_function():
    source=Path(__file__).parents[1]/'cytools_core/templates/ui_common.py.txt'
    tree=ast.parse(source.read_text('utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='label')
    namespace={'tr':lambda text:'translated '+text}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    return namespace['label']

def test_hidden_suffix_keeps_full_original_widget_identity():
    label=label_function()
    assert label('BPM##generate_song')=='translated BPM###BPM##generate_song'
    assert label('Lancer##generate_song')=='translated Lancer###Lancer##generate_song'
    assert label('BPM##clone_style')=='translated BPM###BPM##clone_style'

def test_explicit_identity_and_hidden_labels_are_preserved():
    label=label_function()
    assert label('Progress 50%###progress')=='translated Progress 50%###progress'
    assert label('Progress 80%###progress').split('###')[1]=='progress'
    assert label('##hidden')=='##hidden'
    assert label('Plain')=='translated Plain###Plain'
