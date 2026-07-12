#!/usr/bin/env bash
#
# assign_host_modules.sh —— bk-cmdb「一主机多模块归属」参数化工具
#
# 背景：
#   bk-cmdb 的 cc_ModuleHostConfig 集合中，(bk_module_id, bk_host_id) 是唯一索引，
#   而 (bk_biz_id, bk_host_id) 是非唯一索引，因此同一台主机可同时归属多个模块，
#   甚至跨多个业务（前提是这些模块分属不同业务）。本脚本用于在实验/排障时
#   直接向 cc_ModuleHostConfig 写入「主机 → 模块」关系，支持批量与幂等。
#
# 核心思想：
#   一个模块(module)只属于唯一一个 set，一个 set 只属于唯一一个业务(biz)。
#   因此只要给出 --host 和 --module，biz/set 即可从 cc_ModuleBase 自动反查，
#   天然覆盖「跨业务实验」（指定目标业务的模块 ID 即可）。
#
# 用法：
#   单条归属：
#     ./assign_host_modules.sh --host 7 --module 3
#   显式指定所属业务/set（会校验与模块实际归属是否一致）：
#     ./assign_host_modules.sh --host 7 --module 14 --biz 3 --set 3
#   列出某主机的全部模块关系：
#     ./assign_host_modules.sh --list --host 7
#   批量（每行：host_id,module_id[,biz_id,set_id]，# 开头为注释）：
#     ./assign_host_modules.sh --file assignments.txt
#   移除某主机的模块关系（幂等，可加 --biz/--set 精确匹配，可加 --dry-run 预演）：
#     ./assign_host_modules.sh --remove --host 7 --module 3
#   批量移除：
#     ./assign_host_modules.sh --remove --file assignments.txt
#   预演（不实际写入）：
#     ./assign_host_modules.sh --host 7 --module 3 --dry-run
#
# 环境变量（可选）：
#   MONGO_URI  默认 mongodb://cc:cc@127.0.0.1:27017/cmdb?replicaSet=rs0&authSource=cmdb
#
set -uo pipefail

MONGO_BIN="${MONGO_BIN:-/usr/bin/mongo}"
MONGO_URI="${MONGO_URI:-mongodb://cc:cc@127.0.0.1:27017/cmdb?replicaSet=rs0&authSource=cmdb}"

usage() {
  grep '^#' "$0" | sed 's/^#\s\?//' | sed -n '1,40p'
  exit "${1:-0}"
}

# ---- 参数解析 ----
MODE="assign"          # assign | list | file
REMOVE=0               # 1 = 移除模式
HOST_ID="" MODULE_ID="" BIZ_ID="" SET_ID="" SUPPLIER="" FILE="" DRYRUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --host)    HOST_ID="$2"; shift 2;;
    --module)  MODULE_ID="$2"; shift 2;;
    --biz)     BIZ_ID="$2"; shift 2;;
    --set)     SET_ID="$2"; shift 2;;
    --supplier)SUPPLIER="$2"; shift 2;;
    --file)    FILE="$2"; MODE="file"; shift 2;;
    --list)    MODE="list"; shift;;
    --remove)  REMOVE=1; shift;;
    --dry-run) DRYRUN=1; shift;;
    -h|--help) usage 0;;
    *) echo "未知参数: $1" >&2; usage 1;;
  esac
done

[ -x "$MONGO_BIN" ] || { echo "ERROR: mongo 客户端不存在: $MONGO_BIN" >&2; exit 1; }

# 公共：把数字转成 MongoDB NumberLong 字面量（mongo shell 支持 NumberLong(...)）
nl() { printf 'NumberLong(%s)' "$1"; }

# ---- 模式：列出某主机关系 ----
if [ "$MODE" = "list" ]; then
  [ -n "$HOST_ID" ] || { echo "ERROR: --list 需要 --host" >&2; exit 1; }
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval "
  var hid = NumberLong($HOST_ID);
  var rels = db.cc_ModuleHostConfig.find({bk_host_id: hid}).toArray();
  if (rels.length === 0) { print('host ' + $HOST_ID + ' 在 cc_ModuleHostConfig 中无任何模块关系'); }
  else {
    print('host ' + $HOST_ID + ' 的模块关系（共 ' + rels.length + ' 条）：');
    rels.forEach(function(r){
      var b = db.cc_ApplicationBase.findOne({bk_biz_id: r.bk_biz_id}, {bk_biz_name:1,_id:0});
      var m = db.cc_ModuleBase.findOne({bk_module_id: r.bk_module_id}, {bk_module_name:1,_id:0});
      var s = db.cc_SetBase.findOne({bk_set_id: r.bk_set_id}, {bk_set_name:1,_id:0});
      print('  biz=' + r.bk_biz_id + ' (' + (b?b.bk_biz_name:'?') + '), set=' + r.bk_set_id + ' (' + (s?s.bk_set_name:'?') + '), module=' + r.bk_module_id + ' (' + (m?m.bk_module_name:'?') + ')');
    });
  }
  void 0;
  " 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
  exit 0
fi

# ---- 公共：执行一条归属（在 mongo shell 内）----
# 入参：host, module, biz(可空), set(可空), supplier(可空), dryrun(0/1)
assign_one_js() {
cat <<JS
function assignOne(hostId, moduleId, bizArg, setArg, supArg, dryrun) {
  var host = db.cc_HostBase.findOne({bk_host_id: NumberLong(hostId)}, {bk_host_id:1, bk_supplier_account:1, bk_host_innerip:1, _id:0});
  if (!host) { print('ERROR: host ' + hostId + ' 不存在于 cc_HostBase'); return false; }
  var mod = db.cc_ModuleBase.findOne({bk_module_id: NumberLong(moduleId)}, {bk_module_id:1, bk_set_id:1, bk_biz_id:1, bk_module_name:1, _id:0});
  if (!mod) { print('ERROR: module ' + moduleId + ' 不存在于 cc_ModuleBase'); return false; }

  var sup = supArg || (host.bk_supplier_account) || '0';
  var realSet = setArg ? NumberLong(setArg) : mod.bk_set_id;
  var realBiz = bizArg ? NumberLong(bizArg) : mod.bk_biz_id;

  if (bizArg && mod.bk_biz_id.valueOf() !== NumberLong(bizArg).valueOf())
    print('WARN: 指定的 --biz ' + bizArg + ' 与模块 ' + moduleId + ' 实际所属业务 ' + mod.bk_biz_id + ' 不一致（跨业务实验场景属正常）');
  if (setArg && mod.bk_set_id.valueOf() !== NumberLong(setArg).valueOf())
    print('WARN: 指定的 --set ' + setArg + ' 与模块 ' + moduleId + ' 实际所属 set ' + mod.bk_set_id + ' 不一致');

  var mname = mod.bk_module_name || '';
  var existing = db.cc_ModuleHostConfig.findOne({bk_module_id: NumberLong(moduleId), bk_host_id: NumberLong(hostId)});
  if (existing) {
    print('SKIP: host ' + hostId + ' 已归属 module ' + moduleId + ' (' + mname + ')，跳过');
    return true;
  }
  if (dryrun) {
    print('DRYRUN: 将插入 host ' + hostId + ' -> biz ' + realBiz + ', set ' + realSet + ', module ' + moduleId + ' (' + mname + '), supplier ' + sup);
    return true;
  }
  db.cc_ModuleHostConfig.insertOne({
    bk_biz_id: NumberLong(realBiz),
    bk_host_id: NumberLong(hostId),
    bk_module_id: NumberLong(moduleId),
    bk_set_id: NumberLong(realSet),
    bk_supplier_account: sup
  });
  print('OK: host ' + hostId + ' -> biz ' + realBiz + ', set ' + realSet + ', module ' + moduleId + ' (' + mname + ')');
  return true;
}
JS
}

# ---- 公共：移除一条归属（在 mongo shell 内）----
# 入参：host, module, biz(可空，精确匹配), set(可空，保留位), dryrun(0/1)
remove_one_js() {
cat <<JS
function removeOne(hostId, moduleId, bizArg, setArg, dryrun) {
  var q = {bk_host_id: NumberLong(hostId), bk_module_id: NumberLong(moduleId)};
  if (bizArg) q.bk_biz_id = NumberLong(bizArg);
  var rec = db.cc_ModuleHostConfig.findOne(q);
  if (!rec) {
    print('SKIP: host ' + hostId + ' 在 module ' + moduleId + (bizArg ? ' (biz ' + bizArg + ')' : '') + ' 无关系，跳过');
    return true;
  }
  var m = db.cc_ModuleBase.findOne({bk_module_id: NumberLong(moduleId)}, {bk_module_name:1,_id:0});
  var mname = m ? m.bk_module_name : '';
  if (dryrun) {
    print('DRYRUN: 将删除 host ' + hostId + ' -> biz ' + rec.bk_biz_id + ', module ' + moduleId + ' (' + mname + ')');
    return true;
  }
  var r = db.cc_ModuleHostConfig.deleteOne(q);
  print('OK: 已删除 host ' + hostId + ' -> biz ' + rec.bk_biz_id + ', module ' + moduleId + ' (' + mname + '), deletedCount=' + r.deletedCount);
  return true;
}
JS
}

# ---- 模式：单条移除 ----
if [ "$REMOVE" = "1" ] && [ "$MODE" != "file" ]; then
  [ -n "$HOST_ID" ] || { echo "ERROR: --remove 需要 --host" >&2; exit 1; }
  [ -n "$MODULE_ID" ] || { echo "ERROR: --remove 需要 --module" >&2; exit 1; }
  JS=$(remove_one_js)
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval "$JS
  removeOne($HOST_ID, $MODULE_ID, '${BIZ_ID:-}', '${SET_ID:-}', $DRYRUN);
  void 0;
  " 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
  exit 0
fi

# ---- 模式：单条归属 ----
if [ "$MODE" = "assign" ]; then
  [ -n "$HOST_ID" ] || { echo "ERROR: 需要 --host" >&2; exit 1; }
  [ -n "$MODULE_ID" ] || { echo "ERROR: 需要 --module" >&2; exit 1; }
  JS=$(assign_one_js)
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval "$JS
  assignOne($HOST_ID, $MODULE_ID, '${BIZ_ID:-}', '${SET_ID:-}', '${SUPPLIER:-}', $DRYRUN);
  void 0;
  " 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
  exit 0
fi

# ---- 模式：批量文件（assign 或 remove，由 --remove 决定）----
if [ "$MODE" = "file" ]; then
  [ -f "$FILE" ] || { echo "ERROR: 文件不存在: $FILE" >&2; exit 1; }
  if [ "$REMOVE" = "1" ]; then JS=$(remove_one_js); else JS=$(assign_one_js); fi
  # 把文件内容逐行喂给 mongo（mongo shell 不支持直接读文件循环，这里用进程替换拼成 JS）
  LINES_JS=""
  while IFS= read -r line; do
    # 去注释与空行
    line="${line%%#*}"
    line="$(echo "$line" | tr -d '[:space:]')"
    [ -z "$line" ] && continue
    IFS=',' read -r h m b s <<< "$line"
    [ -z "$h" ] || [ -z "$m" ] && { echo "SKIP 行(格式应为 host,module[,biz,set]): $line" >&2; continue; }
    if [ "$REMOVE" = "1" ]; then
      LINES_JS="${LINES_JS}removeOne($h, $m, '${b:-}', '${s:-}', $DRYRUN);"$'\n'
    else
      LINES_JS="${LINES_JS}assignOne($h, $m, '${b:-}', '${s:-}', '', $DRYRUN);"$'\n'
    fi
  done < "$FILE"
  "$MONGO_BIN" --quiet "$MONGO_URI" --eval "$JS
  $LINES_JS
  void 0;
  " 2>&1 | grep -v 'DeprecationWarning\|future\|WARNING'
  exit 0
fi
