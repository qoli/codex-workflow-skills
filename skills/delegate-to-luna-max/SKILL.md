---
name: delegate-to-luna-max
description: Forward the user's current task to a subagent running gpt-5.6-luna with max reasoning effort, then coordinate and verify its result. Use when the user explicitly invokes this skill or asks Codex to delegate, forward, or hand off a task to a Luna Max subagent.
---

# Delegate to Luna Max

把實質任務交給一個使用 Luna Max 的子代理執行；主代理只負責安全交接、協調、驗收與回報。

## 委派流程

1. 先告知使用者：此 Skill 要把任務委派給 Luna Max 子代理。
2. 從當前請求整理一段自足的交接內容，至少包含：
   - 具體目標與交付物
   - 工作目錄或目標資源
   - 使用者明示的範圍、限制與驗收條件
   - 已知且與任務直接相關的狀態
   - 必須使用的其他 Skill 或規範
3. 不要在交接內容中複製憑證、cookies、完整私人紀錄或其他非必要敏感資料。
4. 在開始實質工作前，呼叫 `spawn_agent`，並固定使用：

```text
fork_turns: "none"
model: "gpt-5.6-luna"
reasoning_effort: "max"
```

   `task_name` 使用簡短、唯一、描述性的 snake_case 名稱；`message` 使用第 2 步整理的自足交接內容。
5. 主代理不要與子代理重複實作同一任務。等待子代理進度；需要補充非敏感背景時，用 `send_message`。需要它修正或補驗時，用 `followup_task` 交回同一個子代理。
6. 子代理完成後，主代理檢查其結果與實際工作區狀態，執行與風險相稱的驗證，再向使用者交付結果。清楚列出任何仍未驗證或未完成的部分。

## 強制條件

- 不得把 `gpt-5.6-luna` 換成其他模型。
- 不得把 `max` reasoning effort 降級。
- 不得在委派失敗、工具不可用或沒有可用子代理槽位時，偷偷改由主代理執行實質任務。
- 委派失敗時，保留並回報原始原因；若情況可能短暫恢復，可做有限次明確重試，仍失敗便停止。
- 不得因委派而擴大使用者授權；破壞性操作、外部發佈、部署或其他高影響動作仍須遵守原任務的權限邊界。
- 只有在子代理實際完成工作且驗收通過後，才宣稱任務完成。

## 多項工作

預設由一個 Luna Max 子代理承接完整任務，以保留上下文一致性。只有當使用者明確要求多子代理或平行處理時，才拆成多個互不重疊的委派；每個子代理仍必須使用相同的 Luna Max 設定。
