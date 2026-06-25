ECOMMERCE_KB = [
    {
        "title": "退款规则",
        "category": "退款售后",
        "keywords": ["退款", "退钱", "原路退回", "到账"],
        "content": "未发货订单可直接申请退款，通常 1-3 个工作日原路退回。已发货订单需先拒收或退回商品，仓库验收后 1-5 个工作日完成退款。",
    },
    {
        "title": "退货换货",
        "category": "退款售后",
        "keywords": ["退货", "换货", "七天无理由", "质量问题"],
        "content": "支持签收后 7 天内无理由退货，商品需保持完好且配件齐全。质量问题可申请换货或退款，需上传照片或视频作为凭证。",
    },
    {
        "title": "物流查询",
        "category": "物流配送",
        "keywords": ["物流", "快递", "配送", "单号", "发货"],
        "content": "订单发货后会生成物流单号，可在订单详情页查询。普通地区通常 2-5 天送达，偏远地区可能延长 1-3 天。",
    },
    {
        "title": "发票开具",
        "category": "支付发票",
        "keywords": ["发票", "抬头", "税号", "电子发票"],
        "content": "下单后可在订单详情申请电子发票。企业发票需填写发票抬头和税号，发票通常在 24 小时内发送到预留邮箱。",
    },
    {
        "title": "商品保修",
        "category": "售后保障",
        "keywords": ["保修", "维修", "质保", "售后"],
        "content": "多数商品享受 12 个月质保。人为损坏、进水、私自拆修不在免费保修范围内，可联系人工客服确认维修方案。",
    },
    {
        "title": "会员积分",
        "category": "会员权益",
        "keywords": ["积分", "会员", "等级", "兑换"],
        "content": "确认收货后积分会自动到账。积分可用于兑换优惠券或部分商品，积分明细可在会员中心查看。",
    },
    {
        "title": "优惠券使用",
        "category": "营销活动",
        "keywords": ["优惠券", "满减", "折扣", "不可用"],
        "content": "优惠券需满足使用门槛和有效期。部分秒杀、预售、特价商品不支持叠加优惠券，具体以结算页展示为准。",
    },
    {
        "title": "投诉与转人工",
        "category": "服务升级",
        "keywords": ["投诉", "人工", "赔偿", "不满意", "差评"],
        "content": "涉及投诉、赔偿、严重服务不满的问题会优先转人工处理。客服主管会根据订单、物流和沟通记录进行核实。",
    },
    {
        "title": "支付失败",
        "category": "支付发票",
        "keywords": ["支付失败", "扣款", "付款", "银行卡"],
        "content": "支付失败可能由余额不足、银行风控、网络异常或支付超时导致。若已扣款但订单未支付成功，通常会在 1-3 个工作日自动退回。",
    },
    {
        "title": "修改地址",
        "category": "物流配送",
        "keywords": ["地址", "修改地址", "收货人", "电话"],
        "content": "未发货订单可在订单详情修改地址。已发货订单无法直接修改，可联系快递尝试改派，改派结果以快递公司处理为准。",
    },
    {
        "title": "订单取消",
        "category": "订单问题",
        "keywords": ["取消订单", "不想要了", "撤销", "关闭订单"],
        "content": "未支付订单可直接取消。已支付未发货订单可申请退款取消，已发货订单需等待收货后按退货流程处理。",
    },
    {
        "title": "商品缺货",
        "category": "商品咨询",
        "keywords": ["缺货", "补货", "无货", "到货通知"],
        "content": "商品缺货时可开启到货提醒。热销商品补货时间不固定，建议关注商品详情页库存状态或联系人工客服确认。",
    },
]

OPEN_DATASETS = [
    {
        "name": "Chinese-Ambiguous-Reference",
        "url": "https://github.com/Alab-NII/Chinese-Ambiguous-Reference",
        "license": "MIT",
        "default_usage": "中文电商客服对话样例和测试问法",
        "production_kb": False,
    },
    {
        "name": "JDDC-Baseline-Seq2Seq",
        "url": "https://github.com/SimonJYang/JDDC-Baseline-Seq2Seq",
        "license": "需人工确认",
        "default_usage": "本地开发测试和问法扩展",
        "production_kb": False,
    },
    {
        "name": "BQ Corpus",
        "url": "https://www.modelscope.cn/datasets/DAMO_NLP/BQ_Corpus",
        "license": "以 ModelScope 页面为准",
        "default_usage": "相似问识别、意图匹配和召回评估",
        "production_kb": False,
    },
    {
        "name": "Customer Support Ticket Dataset",
        "url": "https://www.kaggle.com/datasets/suraj520/customer-support-ticket-dataset",
        "license": "以 Kaggle 页面为准",
        "default_usage": "工单字段、优先级和分类策略参考",
        "production_kb": False,
    },
]
