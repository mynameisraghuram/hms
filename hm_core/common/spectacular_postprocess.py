from __future__ import annotations


def rename_status249enum_to_tenant_status_enum(result: dict, generator, request, public) -> dict:
    """
    drf-spectacular postprocessing hook.

    Renames the generated enum schema component "Status249Enum" -> "TenantStatusEnum"
    and rewrites all references ("$ref") throughout the OpenAPI document.

    This avoids ENUM_NAME_OVERRIDES import-path resolution issues and gives stable naming.
    """
    if not isinstance(result, dict):
        return result

    components = result.get("components") or {}
    schemas = components.get("schemas") or {}

    old = "Status249Enum"
    new = "TenantStatusEnum"

    if old not in schemas:
        return result

    # copy old schema under new name if needed
    if new not in schemas:
        schemas[new] = schemas[old]

    # remove old schema
    if old in schemas:
        del schemas[old]

    # rewrite refs everywhere
    old_ref = f"#/components/schemas/{old}"
    new_ref = f"#/components/schemas/{new}"

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if k == "$ref" and v == old_ref:
                    obj[k] = new_ref
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(result)
    return result
