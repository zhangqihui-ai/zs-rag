/** LightRAG / 图谱抽取常见 entity_type 的中文名与说明 */

export interface EntityTypeMeta {
  labelZh: string
  description: string
}

const TYPE_META: Record<string, EntityTypeMeta> = {
  category: {
    labelZh: '类别',
    description: '对事物、法规条目或主题的归类标签，用于概括其所属领域或性质。',
  },
  concept: {
    labelZh: '概念',
    description: '抽象的知识单元或术语定义，常作为理解文档主题的锚点。',
  },
  organization: {
    labelZh: '组织',
    description: '机构、企业、政府部门等具有组织结构的实体。',
  },
  person: {
    labelZh: '人物',
    description: '自然人或具名角色，如负责人、专家、当事人等。',
  },
  geo: {
    labelZh: '地理',
    description: '地点、区域、国家或地理范围等空间相关实体。',
  },
  location: {
    labelZh: '地点',
    description: '具体地理位置、场所或区域名称。',
  },
  event: {
    labelZh: '事件',
    description: '在特定时间发生的行为、事故、会议或流程节点。',
  },
  technology: {
    labelZh: '技术',
    description: '技术方案、工艺、设备类型或方法论等。',
  },
  artifact: {
    labelZh: '人造物',
    description: '设备、产品、文档、设施等人类创造或定义的物体。',
  },
  naturalobject: {
    labelZh: '自然物',
    description: '自然存在或自然形成的对象，如矿物、灾害因素等。',
  },
  measurement: {
    labelZh: '度量',
    description: '数值、指标、阈值或量化标准，常与监管、检测相关。',
  },
  data: {
    labelZh: '数据',
    description: '结构化或非结构化的数据项、字段或统计结果。',
  },
  actions: {
    labelZh: '行为',
    description: '动作、操作步骤、义务或要求类表述，强调「做什么」。',
  },
  action: {
    labelZh: '行为',
    description: '动作、操作步骤、义务或要求类表述，强调「做什么」。',
  },
  content: {
    labelZh: '内容',
    description: '文档中的主题片段、条款正文或叙述性内容单元。',
  },
  regulation: {
    labelZh: '法规条款',
    description: '规章制度、标准条文或合规要求的表述。',
  },
  method: {
    labelZh: '方法',
    description: '操作程序、处理办法或实施路径。',
  },
  product: {
    labelZh: '产品',
    description: '商品、系统产出物或可交付成果。',
  },
  equipment: {
    labelZh: '设备',
    description: '机器、装置、工具或硬件设施。',
  },
  role: {
    labelZh: '角色',
    description: '职责岗位、职能身份或权限角色。',
  },
  time: {
    labelZh: '时间',
    description: '日期、时段、周期或时间约束。',
  },
  other: {
    labelZh: '其他',
    description: '未能归入常见类别的实体，需结合上下文理解。',
  },
}

export function getEntityTypeMeta(entityType: string | null | undefined): EntityTypeMeta {
  const raw = (entityType || '').trim()
  if (!raw) {
    return {
      labelZh: '未分类',
      description: '抽取结果未标注类型，可在图谱可视化中查看邻接关系辅助理解。',
    }
  }
  const key = raw.toLowerCase()
  const known = TYPE_META[key]
  if (known) {
    return known
  }
  return {
    labelZh: raw,
    description: `由图谱抽取模型标注的类型「${raw}」。将鼠标悬停可结合实体名称与描述理解其在知识库中的含义。`,
  }
}

export function countDistinctEntityTypes(types: Iterable<string | null | undefined>): number {
  const set = new Set<string>()
  for (const t of types) {
    const v = (t || '').trim()
    if (v) {
      set.add(v.toLowerCase())
    }
  }
  return set.size
}
