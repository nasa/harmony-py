import sys

from camel_case_switcher import camel_case_to_underscore
import yaml


def typed_param(yaml_param):
    type_map = {
        'string': 'str',
        'boolean': 'bool',
        'integer': 'int',
        'number': 'float'
    }

    yaml_type = yaml_param['schema']['type']
    py_type = None

    if yaml_type == 'array':
        item_type = type_map[yaml_param['schema']['items']['type']]
        py_type = f"list[{item_type}]"
    else:
        py_type = type_map[yaml_type]

    name = camel_case_to_underscore(yaml_param['name'])
    return f"{name}: {py_type}"


def param_docstring(yaml_param):
    name = camel_case_to_underscore(yaml_param['name'])
    descr = yaml_param['description']
    return f'{name}: {descr}'


def main(schema_filename: str):
    with open(schema_filename, 'r') as schema:
        api = yaml.load(schema, Loader=yaml.Loader)

        do_not_generate = ['collectionId', 'subset']
        params = api['paths']['/collections/{collectionId}/coverage/rangeset']['get']['parameters']
        refs = [p.get('$ref').split('/')[-1] for p in params]
        param_types = [api['components']['parameters'][r] for r in refs if r not in do_not_generate]

        params = [typed_param(pt) for pt in param_types]
        param_docstrings = [param_docstring(pt) for pt in param_types]

        print("def __init__(self, *, " + ", ".join(params) + "):")
        print('    """')
        print('    Parameters:')
        print('    -----------')
        for pds in param_docstrings:
            print('    ' + pds)
            print()
        print()
        print('    """')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python internal/genparams.py harmony_ogc_schema_filename")
        sys.exit(1)

    main(sys.argv[1])
