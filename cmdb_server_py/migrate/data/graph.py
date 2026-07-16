"""
拓扑图 / 图表数据迁移 - 对齐 Go v3.10.50 community/0 种子

承载 Go 在 init_db 阶段产出的「graph / chart」相关集合：
  - cc_TopoGraphics: 拓扑图节点布局（用户保存的拓扑树位置）。Go 仅建空表，运行时由用户写入。
  - cc_ChartConfig:  运营看板内置图表配置，对齐 Go init_chart.go 的 8 条 InnerChartsArr。
  - cc_ChartPosition: 图表在页面上的位置，对齐 Go init_chart.go 的 1 条种子（Host=[3,4,5,6] Inst=[7,8]）。

参考源（bk-cmdb-release-v3.10.50）：
  src/scene_server/admin_server/upgrader/history/v3.0.8/createtable.go            # cc_TopoGraphics 建表
  src/scene_server/admin_server/upgrader/history/y3.6.201911261109/init_chart.go  # cc_ChartConfig / cc_ChartPosition 种子
  src/common/metadata/operation.go                                              # InnerChartsArr / InnerChartsMap / ChartConfig / ChartPosition 结构
  src/common/definitions.go                                                     # 图表 report_type 常量

ID 约定：Go 用 db.NextSequences(cc_ChartConfig, 8) 首次分配 [1..8]，故 config_id 从 1 递增；
         cc_ChartConfig 的 cc_idgenerator 序号由 IDGeneratorMigrate 预留为 8（见 default_data.py），
         本迁移仅写入这 8 条数据，保证后续新建图表的 config_id 从 9 起，与 Go 一致。
"""

from .. import BaseMigrate, get_timestamp, BK_DEFAULT_OWNER_ID, BK_SYSTEM_OPERATOR


# 内置图表，顺序严格对齐 Go 的 metadata.InnerChartsArr
#   [0] biz_module_host_chart      [1] model_and_inst_count
#   [2] host_os_chart              [3] host_biz_chart
#   [4] host_cloud_chart           [5] host_change_biz_chart
#   [6] model_inst_chart          [7] model_inst_change_chart
# config_id 由 1 开始，对应 Go NextSequences(8) 首次返回的 [1..8]。
INNER_CHARTS = [
    {"report_type": "biz_module_host_chart", "name": "", "bk_obj_id": "", "width": "", "chart_type": "", "field": "", "x_axis_count": 0},
    {"report_type": "model_and_inst_count", "name": "", "bk_obj_id": "", "width": "", "chart_type": "", "field": "", "x_axis_count": 0},
    {"report_type": "host_os_chart", "name": "按操作系统类型统计", "bk_obj_id": "host", "width": "50", "chart_type": "pie", "field": "bk_os_type", "x_axis_count": 10},
    {"report_type": "host_biz_chart", "name": "按业务统计", "bk_obj_id": "host", "width": "50", "chart_type": "bar", "field": "", "x_axis_count": 10},
    {"report_type": "host_cloud_chart", "name": "按云区域统计", "bk_obj_id": "host", "width": "100", "chart_type": "bar", "field": "bk_cloud_id", "x_axis_count": 20},
    {"report_type": "host_change_biz_chart", "name": "主机数量变化趋势", "bk_obj_id": "", "width": "100", "chart_type": "", "field": "", "x_axis_count": 20},
    {"report_type": "model_inst_chart", "name": "实例数量统计", "bk_obj_id": "", "width": "50", "chart_type": "bar", "field": "", "x_axis_count": 10},
    {"report_type": "model_inst_change_chart", "name": "实例变更统计", "bk_obj_id": "", "width": "50", "chart_type": "bar", "field": "", "x_axis_count": 10},
]


class GraphMigrate(BaseMigrate):
    """拓扑图 / 图表数据迁移 - 对齐 Go cc_TopoGraphics / cc_ChartConfig / cc_ChartPosition"""

    def migrate(self) -> None:
        self._migrate_topo_graphics()
        self._migrate_chart_config()
        self._migrate_chart_position()

    def _migrate_topo_graphics(self) -> None:
        # Go 仅创建空表（createtable.go），拓扑布局由用户在前端保存时写入
        self.ensure_collection("cc_TopoGraphics")

    def _migrate_chart_config(self) -> None:
        self.ensure_collection("cc_ChartConfig")
        ts = get_timestamp()
        for idx, chart in enumerate(INNER_CHARTS, start=1):
            data = {
                "config_id": idx,
                "report_type": chart["report_type"],
                "name": chart["name"],
                "bk_obj_id": chart["bk_obj_id"],
                "width": chart["width"],
                "chart_type": chart["chart_type"],
                "field": chart["field"],
                "x_axis_count": chart["x_axis_count"],
                "create_time": ts,
                "bk_supplier_account": BK_DEFAULT_OWNER_ID,
            }
            self.upsert("cc_ChartConfig", data, ["config_id", "bk_supplier_account"])

    def _migrate_chart_position(self) -> None:
        # 对齐 Go init_chart.go: Position.Host = idArr[2:6] = [3,4,5,6], Position.Inst = idArr[6:] = [7,8]
        self.ensure_collection("cc_ChartPosition")
        data = {
            "bk_biz_id": 0,
            "position": {"host": [3, 4, 5, 6], "inst": [7, 8]},
            "bk_supplier_account": BK_DEFAULT_OWNER_ID,
        }
        self.upsert("cc_ChartPosition", data, ["bk_biz_id", "bk_supplier_account"])


def run_graph_migrate(db) -> None:
    """执行拓扑图 / 图表数据迁移"""
    GraphMigrate(db).migrate()
    print("Graph (TopoGraphics/ChartConfig/ChartPosition) migrate completed!")
