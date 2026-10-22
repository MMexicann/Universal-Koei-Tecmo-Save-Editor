"""Keep excluded runtime compiler tools from being reintroduced by an alias.

PyInstaller 6.22.3's generic distutils hook aliases setuptools._distutils even
when distutils is an ExcludedModule. Our precompiled preview stack excludes
all three compiler roots; never create those aliases for this build.
"""


def pre_safe_import_module(api):
    from PyInstaller.lib.modulegraph.modulegraph import ExcludedModule

    if api.module_name != 'distutils':
        raise ValueError('Unexpected compiler-exclusion hook target.')
    for module in ('setuptools', 'distutils', 'pkg_resources'):
        if not isinstance(api.module_graph.find_node(module), ExcludedModule):
            raise ValueError(f'Required runtime compiler exclusion is missing: {module}')
