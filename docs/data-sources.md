# 知识库与公开数据说明

## 内置知识库

系统默认内置中文电商客服种子知识库，覆盖退款、退货换货、物流、发票、保修、会员积分、优惠券、投诉、支付失败、修改地址、订单取消、商品缺货等场景。

这些内容为项目自建演示知识，默认可用于本系统运行。

## 公开数据

| 数据源 | 地址 | 建议用途 | 是否默认进入生产知识库 |
| --- | --- | --- | --- |
| Chinese-Ambiguous-Reference | https://github.com/Alab-NII/Chinese-Ambiguous-Reference | 中文电商客服对话样例、测试问法 | 否 |
| JDDC-Baseline-Seq2Seq | https://github.com/SimonJYang/JDDC-Baseline-Seq2Seq | 本地开发测试、问法扩展 | 否 |
| BQ Corpus | https://www.modelscope.cn/datasets/DAMO_NLP/BQ_Corpus | 相似问识别、意图匹配、召回评估 | 否 |
| Customer Support Ticket Dataset | https://www.kaggle.com/datasets/suraj520/customer-support-ticket-dataset | 工单字段、分类和优先级参考 | 否 |

外部数据导入前必须确认许可证、来源和用途。默认产品运行只依赖自建种子知识库，避免许可证风险。
