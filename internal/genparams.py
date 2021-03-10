import sys

from camel_case_switcher import camel_case_to_underscore
import yaml


def canonical_name(yaml_param):
    name_map = {
        'outputcrs': 'crs'
    }

    print(yaml_param)
    name = yaml_param['name']
    return name_map.get(name, camel_case_to_underscore(name))


def canonical_type(yaml_param):
    type_map = {
        'string': 'str',
        'boolean': 'bool',
        'integer': 'int',
        'number': 'float'
    }

    py_type = None
    yaml_type = yaml_param['schema']['type']
    if yaml_type == 'array':
        item_type = type_map[yaml_param['schema']['items']['type']]
        py_type = f"list[{item_type}]"
    else:
        py_type = type_map[yaml_type]

    return py_type


def param_docstring(yaml_param):
    name = canonical_name(yaml_param)
    descr = yaml_param['description']
    return f'{name}: {descr}'


def main(schema_filename: str):
    with open(schema_filename, 'r') as schema:
        api = yaml.load(schema, Loader=yaml.Loader)

        do_not_generate = ['collectionId', 'subset']

        params = api['paths']['/collections/{collectionId}/coverage/rangeset']['get']['parameters']
        refs = [p.get('$ref').split('/')[-1] for p in params]
        param_types = [api['components']['parameters'][r] for
                       r in refs if r not in do_not_generate]

        params = [f'{canonical_name(pt)}: {canonical_type(pt)}' for pt in param_types]
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
