/* ============================================================
 * config.js —— 高德地图与校园基础配置
 * 注意：本文件必须最先加载，且 securityJsCode 要在 loader.js 之前注入
 * ============================================================ */

window.AMAP_CONFIG = {
  key: "c747dded701673039c2f37176a2b47c9",
  securityJsCode: "65fc5044e4e373f2f9ec39237c78cf8b",
  version: "2.0"
};

window.CAMPUS = {
  name: "兰州交通大学（安宁校区）",
  center: [103.723371, 36.105326],   // 高德地理编码结果（GCJ-02）
  zoom: 17,
  pitch: 45,
  rotation: 0
};

/* 点位功能类别：用于着色、分组统计与分区聚合 */
window.FUNC_TYPES = {
  dorm:    { label: "宿舍区",   color: "#7F77DD" },
  teach:   { label: "教学区",   color: "#185FA5" },
  canteen: { label: "食堂",     color: "#D85A30" },
  gate:    { label: "校门接驳", color: "#0F6E56" },
  library: { label: "图书馆",   color: "#534AB7" },
  sport:   { label: "运动场",   color: "#639922" },
  other:   { label: "其他",     color: "#888780" }
};

/* 状态阈值：按 车辆数/容量 判定 */
window.STATUS_RULE = {
  lowRatio: 0.15,   // 低于 15% 视为缺车
  highRatio: 0.80   // 高于 80% 视为淤积
};
