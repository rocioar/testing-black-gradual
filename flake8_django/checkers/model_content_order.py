from ast import Assign, Call, ClassDef, FunctionDef
from functools import partial

from .base_model_checker import BaseModelChecker
from .issue import Issue


class DJ12(Issue):
    code = 'DJ12'
    description = (
        'Order of model inner classes and standard methods does not follow '
        'Django style guide: {elem_type} should come before {before}'
    )

    def __init__(self, elem, elem_type, before):
        super().__init__(elem.lineno, elem.col_offset, None)
        self.description = self.description.format(
            elem_type=elem_type,
            before=before,
        )


def is_assignment_call(node):
    # check if assigning the return value of a function call to a target which is not in all uppercase letters
    # (because that would be a constant)
    return isinstance(node, Assign) and isinstance(node.value, Call) and not node.targets[0].id.isupper()


def is_manager_declaration(node):
    return isinstance(node, Assign) and getattr(node.targets[0], 'id', None) == 'objects'


def is_meta_declaration(node):
    return isinstance(node, ClassDef) and node.name == 'Meta'


def is_method(node, method_name=None):
    if method_name is None:
        return isinstance(node, FunctionDef)
    return isinstance(node, FunctionDef) and node.name == method_name


class ModelContentOrderChecker(BaseModelChecker):
    model_name_lookup = 'Model'

    FIELD_DECLARATION = 'field declaration'
    MANAGER_DECLARATION = 'manager declaration'
    META_CLASS = 'Meta class'
    STR_METHOD = '__str__ method'
    SAVE_METHOD = 'save method'
    GET_ABSOLUTE_URL_METHOD = 'get_absolute_url method'
    CUSTOM_METHOD = 'custom method'

    MODEL_CONTENT_TYPE_EXPECTED_ORDER = {
        FIELD_DECLARATION: 0,
        MANAGER_DECLARATION: 1,
        META_CLASS: 2,
        STR_METHOD: 3,
        SAVE_METHOD: 4,
        GET_ABSOLUTE_URL_METHOD: 5,
        CUSTOM_METHOD: 6,
    }
    CONTENT_TYPE_CHECKS = [
        (is_assignment_call, FIELD_DECLARATION),
        (is_manager_declaration, MANAGER_DECLARATION),
        (is_meta_declaration, META_CLASS),
        (partial(is_method, method_name='__str__'), STR_METHOD),
        (partial(is_method, method_name='save'), SAVE_METHOD),
        (partial(is_method, method_name='get_absolute_url'), GET_ABSOLUTE_URL_METHOD),
        (is_method, CUSTOM_METHOD),
    ]

    def checker_applies(self, node):
        for base in node.bases:
            if self.is_model_name_lookup(base) or self.is_models_name_lookup_attribute(base):
                return True
        return False

    def run(self, node):
        if not self.checker_applies(node):
            return

        return self.get_issues(node)

    def get_issues(self, node):
        elements_type_found = []
        for element in node.body:
            element_type = self.get_element_type(element)
            if not element_type:
                continue

            element_type_in_wrong_order = self.find_element_type_in_wrong_order(element_type, elements_type_found)
            if element_type_in_wrong_order:
                yield DJ12(
                    element,
                    element_type,
                    element_type_in_wrong_order,
                )
            else:
                elements_type_found.append(element_type)

    def get_element_type(self, element):
        for check, element_type in self.CONTENT_TYPE_CHECKS:
            if check(element):
                return element_type

    def find_element_type_in_wrong_order(self, element_type, elements_type_found):
        current_element_type_order = self.get_expected_order(element_type)
        for element_type in elements_type_found:
            if self.get_expected_order(element_type) > current_element_type_order:
                return element_type

    def get_expected_order(self, element_type):
        return self.MODEL_CONTENT_TYPE_EXPECTED_ORDER.get(element_type)
