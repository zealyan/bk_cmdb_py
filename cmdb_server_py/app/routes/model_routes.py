"""模型管理路由门面（对齐 bk-cmdb Go 端 ``scene_server/topo_server/service/*`` + ``logics/model/*``）。

本文件是「模型管理」模块的 HTTP 入口，仅做参数解析与响应封装，业务逻辑全部委托给
``app.core.model``。蓝图以 ``/api/v3`` 前缀注册，路径与前端 ``store/modules/api/object-*.js``
严格对齐：

  object(模型)        cc_ObjDes
  objectattr(属性)    cc_ObjAttDes
  objectclassification(分类)  cc_ObjClassification
  objectassociation(模型关联) cc_ObjAsst
  associationtype(关联类型)   cc_AsstDes
  objectunique(唯一规则)       cc_ObjectUnique
  objectattgroup(属性分组)     cc_PropertyGroup
"""

from flask import Blueprint, request

from app.core import model as core
from app.routes.object_routes import make_response, _parse_body

model_bp = Blueprint('model', __name__)


def _ok(data=None):
    return make_response(data=data)


def _err(e):
    code = getattr(e, "code", 500)
    return make_response(result=False, code=code, message=str(e))


def _wrap(fn, *args, **kwargs):
    try:
        return _ok(fn(*args, **kwargs))
    except core.ModelError as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return make_response(result=False, code=500, message=str(e))


# --------------------------------------------------------------------------- #
# Model（object）
# --------------------------------------------------------------------------- #
@model_bp.route('/create/object', methods=['POST'])
def api_create_object():
    return _wrap(core.create_model, _parse_body())


@model_bp.route('/delete/object/<int:rid>', methods=['DELETE'])
def api_delete_object(rid):
    return _wrap(core.delete_model, rid)


@model_bp.route('/update/object/<int:rid>', methods=['PUT'])
def api_update_object(rid):
    return _wrap(core.update_model, rid, _parse_body())


@model_bp.route('/find/object', methods=['POST'])
def api_find_object():
    return _wrap(core.search_model, _parse_body())


@model_bp.route('/find/objecttopology', methods=['POST'])
def api_find_object_topo():
    return _wrap(core.search_model_topo, _parse_body())


# --------------------------------------------------------------------------- #
# Attribute（objectattr）
# --------------------------------------------------------------------------- #
@model_bp.route('/create/objectattr', methods=['POST'])
def api_create_objectattr():
    return _wrap(core.create_model_attributes, _parse_body())


@model_bp.route('/create/objectattr/biz/<int:biz_id>', methods=['POST'])
def api_create_objectattr_biz(biz_id):
    body = _parse_body()
    if isinstance(body, list):
        for it in body:
            it["bk_biz_id"] = biz_id
    else:
        body["bk_biz_id"] = biz_id
    return _wrap(core.create_model_attributes, body)


@model_bp.route('/delete/objectattr/<int:rid>', methods=['DELETE'])
def api_delete_objectattr(rid):
    return _wrap(core.delete_model_attributes, rid)


@model_bp.route('/update/objectattr/<int:rid>', methods=['PUT'])
def api_update_objectattr(rid):
    return _wrap(core.update_model_attributes, rid, _parse_body())


@model_bp.route('/update/objectattr/biz/<int:biz_id>/id/<int:rid>', methods=['PUT'])
def api_update_objectattr_biz(biz_id, rid):
    body = _parse_body()
    body["bk_biz_id"] = biz_id
    return _wrap(core.update_model_attributes, rid, body)


@model_bp.route('/update/objectattr/index/<obj_id>/<property_id>', methods=['PUT', 'POST'])
def api_update_objectattr_index(obj_id, property_id):
    body = _parse_body()
    index = body.get("bk_property_index", body.get("index", 0))
    return _wrap(core.update_model_attribute_index, obj_id, property_id, index)


# --------------------------------------------------------------------------- #
# Classification（objectclassification）
# --------------------------------------------------------------------------- #
@model_bp.route('/create/objectclassification', methods=['POST'])
def api_create_classification():
    return _wrap(core.create_classification, _parse_body())


@model_bp.route('/delete/objectclassification/<int:rid>', methods=['DELETE'])
def api_delete_classification(rid):
    return _wrap(core.delete_classification, rid)


@model_bp.route('/update/objectclassification/<int:rid>', methods=['PUT'])
def api_update_classification(rid):
    return _wrap(core.update_classification, rid, _parse_body())


@model_bp.route('/object/statistics', methods=['GET'])
def api_object_statistics():
    return _wrap(core.object_statistics, request.args.to_dict())


# --------------------------------------------------------------------------- #
# Association（objectassociation）
# --------------------------------------------------------------------------- #
@model_bp.route('/find/objectassociation', methods=['POST'])
def api_find_object_association():
    return _wrap(core.search_object_association, _parse_body())


@model_bp.route('/create/objectassociation', methods=['POST'])
def api_create_object_association():
    return _wrap(core.create_object_association, _parse_body())


@model_bp.route('/update/objectassociation/<int:rid>', methods=['PUT'])
def api_update_object_association(rid):
    return _wrap(core.update_object_association, rid, _parse_body())


@model_bp.route('/delete/objectassociation/<int:rid>', methods=['DELETE'])
def api_delete_object_association(rid):
    return _wrap(core.delete_object_association, rid)


# --------------------------------------------------------------------------- #
# AssociationType（associationtype）
# --------------------------------------------------------------------------- #
@model_bp.route('/find/associationtype', methods=['POST'])
def api_find_association_type():
    return _wrap(core.search_association_type, _parse_body())


@model_bp.route('/create/associationtype', methods=['POST'])
def api_create_association_type():
    return _wrap(core.create_association_type, _parse_body())


@model_bp.route('/update/associationtype/<int:rid>', methods=['PUT'])
def api_update_association_type(rid):
    return _wrap(core.update_association_type, rid, _parse_body())


@model_bp.route('/delete/associationtype/<int:rid>', methods=['DELETE'])
def api_delete_association_type(rid):
    return _wrap(core.delete_association_type, rid)


@model_bp.route('/find/topoassociationtype', methods=['POST'])
def api_find_topo_association_type():
    return _wrap(core.find_topo_association_type, _parse_body())


# --------------------------------------------------------------------------- #
# Unique（objectunique）
# --------------------------------------------------------------------------- #
@model_bp.route('/create/objectunique/object/<obj_id>', methods=['POST'])
def api_create_object_unique(obj_id):
    return _wrap(core.create_object_unique, obj_id, _parse_body())


@model_bp.route('/update/objectunique/object/<obj_id>/unique/<int:rid>', methods=['PUT'])
def api_update_object_unique(obj_id, rid):
    return _wrap(core.update_object_unique, obj_id, rid, _parse_body())


@model_bp.route('/delete/objectunique/object/<obj_id>/unique/<int:rid>', methods=['POST'])
def api_delete_object_unique(obj_id, rid):
    return _wrap(core.delete_object_unique, obj_id, rid)


@model_bp.route('/find/objectunique/object/<obj_id>', methods=['POST'])
def api_find_object_unique(obj_id):
    return _wrap(core.search_object_unique, obj_id)


# --------------------------------------------------------------------------- #
# PropertyGroup（objectattgroup）
# --------------------------------------------------------------------------- #
@model_bp.route('/create/objectattgroup', methods=['POST'])
def api_create_objectattgroup():
    return _wrap(core.create_property_group, _parse_body())


@model_bp.route('/find/objectattgroup/object/<obj_id>', methods=['POST'])
def api_find_objectattgroup(obj_id):
    return _wrap(core.search_property_group, obj_id)


@model_bp.route('/update/objectattgroup', methods=['PUT'])
def api_update_objectattgroup():
    return _wrap(core.update_property_group, _parse_body())


@model_bp.route('/update/objectattgroup/groupindex', methods=['PUT'])
def api_update_objectattgroup_index():
    return _wrap(core.update_property_group_index, _parse_body())


@model_bp.route('/delete/objectattgroup/<int:rid>', methods=['DELETE'])
def api_delete_objectattgroup(rid):
    return _wrap(core.delete_property_group, rid)


@model_bp.route('/objectatt/group/property', methods=['PUT'])
def api_objectatt_group_property():
    return _wrap(core.bind_group_property, _parse_body())


@model_bp.route('/delete/objectattgroupasst/object/<obj_id>/property/<property_id>/group/<group_id>', methods=['DELETE'])
def api_delete_objectattgroupasst(obj_id, property_id, group_id):
    return _wrap(core.unbind_group_property, obj_id, property_id, group_id)
