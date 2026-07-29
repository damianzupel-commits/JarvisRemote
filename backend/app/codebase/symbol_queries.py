"""Queries de tree-sitter para extraer símbolos (funciones/métodos, clases,
imports) por lenguaje. Cada entrada es un string de query en la sintaxis de
tree-sitter (ver https://tree-sitter.github.io/tree-sitter/using-parsers#query-syntax),
con capturas nombradas `@function`, `@class`/`@type`, `@import` que
`indexer.py` interpreta genéricamente sin necesitar saber los nombres de nodo
específicos de cada gramática.

Se probaron a mano contra snippets reales de cada lenguaje (ver
tests/test_codebase_indexer.py) -- si una gramática nueva se agrega a
`languages.LANGUAGE_TO_GRAMMAR`, hace falta agregarle su entrada acá o cae al
extractor regex genérico.

Capturas que empiezan con "_" (ej. `@_require_fn`) son auxiliares -- existen
solo para que un predicado tipo `#eq?` pueda filtrar el patrón (acá, "solo
llamadas a la función `require`, no cualquier call_expression"), no
representan un símbolo real. `indexer.py` las descarta explícitamente.
"""

from __future__ import annotations

SYMBOL_QUERIES: dict[str, str] = {
    "python": """
        (function_definition name: (identifier) @function)
        (class_definition name: (identifier) @class)
        (import_statement) @import
        (import_from_statement) @import
    """,
    "javascript": """
        (function_declaration name: (identifier) @function)
        (method_definition name: (property_identifier) @function)
        (class_declaration name: (identifier) @class)
        (variable_declarator name: (identifier) @function value: (arrow_function))
        (variable_declarator name: (identifier) @function value: (function_expression))
        (import_statement) @import
        (call_expression
            function: (identifier) @_require_fn
            arguments: (arguments (string) @_require_arg)
            (#eq? @_require_fn "require")) @import
    """,
    "typescript": """
        (function_declaration name: (identifier) @function)
        (method_definition name: (property_identifier) @function)
        (class_declaration name: (type_identifier) @class)
        (interface_declaration name: (type_identifier) @class)
        (variable_declarator name: (identifier) @function value: (arrow_function))
        (variable_declarator name: (identifier) @function value: (function_expression))
        (import_statement) @import
        (call_expression
            function: (identifier) @_require_fn
            arguments: (arguments (string) @_require_arg)
            (#eq? @_require_fn "require")) @import
    """,
    "tsx": """
        (function_declaration name: (identifier) @function)
        (method_definition name: (property_identifier) @function)
        (class_declaration name: (type_identifier) @class)
        (interface_declaration name: (type_identifier) @class)
        (variable_declarator name: (identifier) @function value: (arrow_function))
        (variable_declarator name: (identifier) @function value: (function_expression))
        (import_statement) @import
        (call_expression
            function: (identifier) @_require_fn
            arguments: (arguments (string) @_require_arg)
            (#eq? @_require_fn "require")) @import
    """,
    "java": """
        (method_declaration name: (identifier) @function)
        (constructor_declaration name: (identifier) @function)
        (class_declaration name: (identifier) @class)
        (interface_declaration name: (identifier) @class)
        (import_declaration) @import
    """,
    "kotlin": """
        (function_declaration (simple_identifier) @function)
        (class_declaration (type_identifier) @class)
        (import_header) @import
    """,
    "go": """
        (function_declaration name: (identifier) @function)
        (method_declaration name: (field_identifier) @function)
        (type_spec name: (type_identifier) @class type: (struct_type))
        (type_spec name: (type_identifier) @class type: (interface_type))
        (import_spec) @import
    """,
    "rust": """
        (function_item name: (identifier) @function)
        (struct_item name: (type_identifier) @class)
        (enum_item name: (type_identifier) @class)
        (trait_item name: (type_identifier) @class)
        (impl_item type: (type_identifier) @class)
        (use_declaration) @import
    """,
    "c": """
        (function_definition declarator: (function_declarator declarator: (identifier) @function))
        (struct_specifier name: (type_identifier) @class)
        (preproc_include) @import
    """,
    "cpp": """
        (function_definition declarator: (function_declarator declarator: (identifier) @function))
        (function_definition declarator: (function_declarator declarator: (field_identifier) @function))
        (class_specifier name: (type_identifier) @class)
        (struct_specifier name: (type_identifier) @class)
        (preproc_include) @import
    """,
    "csharp": """
        (method_declaration name: (identifier) @function)
        (constructor_declaration name: (identifier) @function)
        (class_declaration name: (identifier) @class)
        (interface_declaration name: (identifier) @class)
        (using_directive) @import
    """,
    "ruby": """
        (method name: (identifier) @function)
        (class name: (constant) @class)
        (module name: (constant) @class)
    """,
    "php": """
        (function_definition name: (name) @function)
        (method_declaration name: (name) @function)
        (class_declaration name: (name) @class)
        (interface_declaration name: (name) @class)
    """,
    "swift": """
        (function_declaration name: (simple_identifier) @function)
        (class_declaration name: (type_identifier) @class)
        (import_declaration) @import
    """,
}
