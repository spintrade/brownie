from copy import deepcopy
from docopt import docopt
import os
import re
import shutil
import sys
import json

from lib.test import run_test
from lib.services import color
from lib.services.compiler import compile_contracts

from lib.components.bytecode import get_coverage_map

__doc__ = """Usage: brownie coverage [<filename>] [options]

Arguments:
  <filename>         Only run tests from a specific file

Options:
  --help             Display this message
  --verbose          Enable verbose reporting

Coverage will modify the contracts and run your unit tests to get estimate
of how much coverage you have.  so simple..."""

def main():
    args = docopt(__doc__)

    if args['<filename>']:
        name = args['<filename>'].replace(".py", "")
        if not os.path.exists("tests/{}.py".format(name)):
            sys.exit(
                "{0[bright red]}ERROR{0}: Cannot find".format(color) +
                " {0[bright yellow]}tests/{1}.py{0}".format(color, name)
            )
        test_files = [name]
    else:
        test_files = [i[:-3] for i in os.listdir("tests") if i[-3:] == ".py"]
        test_files.remove('__init__')
    
    compiled = deepcopy(compile_contracts())
    fn_map, line_map = get_coverage_map(compiled)

    for filename in test_files:
        history, tb = run_test(filename)
        if tb:
            sys.exit(
                "\n{0[error]}ERROR{0}: Cannot ".format(color) +
                "calculate coverage while tests are failing\n\n" + 
                "Exception info for {}:\n{}".format(tb[0], tb[1])
            )
        for tx in history:
            if not tx.receiver:
                continue
            for i in range(len(tx.trace)):
                t = tx.trace[i]
                pc = t['pc']
                name = t['contractName']
                if not name:
                    continue
                try:
                    fn = next(i for i in fn_map[name] if pc in i['pc'])
                    fn['tx'].add(tx)
                    if t['op']!="JUMPI":
                        ln = next(i for i in line_map[name] if pc in i['pc'])
                        ln['tx'].add(tx)
                        continue
                    ln = next(i for i in line_map[name] if pc==i['jump'])
                    if tx not in ln['tx']:
                        continue
                    key = 'false' if tx.trace[i+1]['pc'] == pc+1 else 'true'
                    ln[key].add(tx)
                except StopIteration:
                    continue

    for ln in [x for v in line_map.values() for x in v]:
        if ln['jump']:
            ln['true'] = len(ln['true'])
            ln['false'] = len(ln['false'])
        ln['tx'] = len(ln['tx'])
        del ln['pc']

    for contract in fn_map:
        for fn in fn_map[contract].copy():
            print(fn['name'])
            fn['tx'] = len(fn['tx'])
            del fn['pc']
            line_fn = [i for i in line_map[contract] if i['name']==fn['name']]
            if not fn['tx'] or not [i for i in line_fn if i['tx']]:
                for ln in line_fn:
                    line_map[contract].remove(ln)
            elif line_fn:
                fn_map[contract].remove(fn)
        fn_map[contract].extend(line_map[contract])
    
    json.dump(fn_map, open('coverage.json', 'w'), sort_keys=True, indent=4)