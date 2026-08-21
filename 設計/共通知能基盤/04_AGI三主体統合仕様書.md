# AGI三主体統合仕様書

## 0. 目的

本書は、HDS・ミニドラ・記憶を一つのAGI Runtimeとして接続する共通契約を定める。

主体は次の三つで固定する。

```text
AGI = HDS + ミニドラ + 記憶
```

第4主体を追加しない。
HDSコンパイラ、検索器、Adapter、検証器等は三主体の責任下に置かれる機能である。

## 1. 三主体の責任

| 主体 | 主責任 | 持たない権限 |
|---|---|---|
| HDS | 世界入力、Frame、判断、Feedback、Commit、因果帰属、記憶更新承認 | ミニドラ内部計算の実装詳細 |
| ミニドラ | HDS入力に対する計算、仮説、推論、計画、候補生成 | 世界への最終Commit、正本記憶の独断更新 |
| 記憶 | 事前知識・実行知識・定石・蒸留知識・反例・Failureの可変保持 | 目的変更、候補生成、最終採否 |

## 2. 世界との境界

世界との直接境界はHDSが持つ。

```text
World
  ↓
 HDS
  ↓
HDS Compiler
  ↓
Minidora
  ↓
 HDS
  ↓
World
```

記憶はこの循環の内部でHDSとミニドラの判断・計算を支える。

```text
        ┌──── 記憶 ────┐
        ↓              ↑
World → HDS → Minidora → HDS → World
```

## 3. オフライン事前記憶生成Loop

本構成では、実行前に知識を蓄える。

```text
利用可能な公式サンプル
正解 / 成功過程 / 状態遷移
        ↓
       HDS
  完全解析・構造化
        ↓
局所定石・機構・反例
        ↓
   水平引き算
        ↓
    蒸留知識
        ↓
  HDS Gate / 承認
        ↓
   Prior Memory
```

事前記憶生成は競技Runtimeとは分離するが、同じHDS責任原則を使う。

目的は「答えを捨てて汎化する」ことではない。
既知解・定石・蒸留知識を同時に保持し、既知には直接性、未知には構造転用を使い分ける。

## 4. オンライン実行Loop

### Step 1 世界受領

HDSが現在世界を受け取る。

### Step 2 観測・Frame

HDSが観測、対象化、目的、価値、リスク、境界、Open Termを確定する。

### Step 3 記憶要求

HDSが現在Frameから記憶検索条件を作る。

### Step 4 記憶返却

記憶主体が既知解、定石、機構、蒸留知識、反例、Failure Signature等を候補として返す。

### Step 5 HDS記憶監査

HDSがscope、成立条件、反例、provenance、現在状態との整合を確認し、ミニドラへ渡す記憶集合を確定する。

### Step 6 HDSコンパイル

HDS Compilerが世界記述、目的、問い、許可記憶、作用集合、反証条件等を一つの計算要求パケットへ閉じる。

### Step 7 ミニドラ計算

ミニドラがLayer-0 / P / Rにより、仮説、反対仮説、予測、計画、作用候補を生成する。

### Step 8 HDS監査

HDSが候補をGateへ通す。

### Step 9 FeedbackまたはCommit

不十分ならミニドラへFeedbackして再計算する。
十分ならHDSが外部作用をCOMMITする。

### Step 10 世界作用

Adapterを介してARC世界へ作用する。

### Step 11 再観測・因果帰属

HDSが更新後世界を再受領し、差分と原因を監査する。

### Step 12 記憶更新

HDSが記憶のADD / REVISE / MERGE / SPLIT / REPLACE / INVALIDATE / DELETE / ROLLBACK / ARCHIVEを承認する。

その更新が次のLoopへ影響する。

## 5. 内部Feedback Loop

外部作用前に、HDSとミニドラは複数回循環してよい。

```text
HDS
 ↓
ミニドラ
 ↓
候補
 ↓
HDS
 ├ 反証追加
 ├ 記憶差替え
 ├ 目的再固定
 ├ 条件追加
 ├ 代替仮説要求
 ├ 追加観測要求
 └ 棄却
 ↓
ミニドラ再計算
```

この循環は、HDSがCOMMIT / SUSPEND / FAIL / STOPのいずれかを確定するまで続けられる。

## 6. Self-Commit禁止

候補生成系が自分の候補をそのまま採用・作用・正本更新してはならない。

```text
MinidoraCandidate
    !=
HDSCommit
```

同一プロセスや同一プログラム内に実装しても、論理承認点を分ける。

最低限、次の三つを分離する。

```text
compute_or_candidate_generation
judgement_or_commit
mutable_active_memory
```

## 7. 記憶の因果循環

三主体循環が成立するには、記憶が未来の判断を変えなければならない。

```text
経験
 ↓
HDS因果帰属
 ↓
Memory更新
 ↓
次回HDS Frame / 検索結果が変化
 ↓
Minidora入力が変化
 ↓
候補・判断・作用が変化
```

単なるログ追記では三主体循環成立とみなさない。

## 8. 定石利用モデル

基本方針は「毎回ゼロから全探索」ではない。

```text
現在状態
 ↓
HDS構造認識
 ↓
Prior Memory照合
 ├ 完全一致 → 既知解・既知定石を優先
 ├ 部分一致 → 定石・機構を合成
 └ 一致なし → 蒸留知識 + 探索
 ↓
不足部分だけ計算・観測
```

成功した探索結果はHDSで再解析し、将来の定石・蒸留知識候補へ戻す。

## 9. ARC2 / ARC3への射影

共通知能基盤はARC2 / ARC3で分岐しない。

```text
共通知能基盤
      ↓
  Domain Adapter
   ├ ARC2 Adapter
   └ ARC3 Adapter
```

ARC固有なのは原則として次だけである。

- 入力形式
- 観測形式
- 利用可能作用
- 出力形式
- score / success条件
- 公式sampleのsource
- 実行制約
- Kaggle / ARC固定API

HDS、ミニドラ、記憶の責任境界をARC固有条件でforkしない。

## 10. ARC2とARC3の差分

ARC2は主として静的入力→出力問題としてAdapterを構成する。
ARC3は動的世界→作用→結果→再観測のAction Loopを持つAdapterを構成する。

この違いはDomain Adapterの差であり、AGI三主体の差ではない。

## 11. 日本語基底

内部正本は日本語とする。

```text
内部認知・設計・記憶・判断
= 日本語

外部SDK / Python / Kaggle / ARC固定記号
= Adapter境界で必要な原語を保持
```

英語正本を作ってから日本語へ翻訳する二重管理を標準運用にしない。

## 12. 権限不変条件

1. 世界入力の最初の認知主体はHDSである。
2. 世界作用の最終確定主体はHDSである。
3. HDSコンパイラはHDSに属する。
4. ミニドラはLLM計算主体である。
5. 記憶は可変判断根拠保持主体である。
6. ミニドラはHDSを迂回して世界へ作用しない。
7. ミニドラはHDSを迂回して正本記憶を更新しない。
8. 記憶は自分自身で目的・判断・作用を決めない。
9. ARC Adapterは共通知能基盤の責任境界を上書きしない。

## 13. 最小統合適合試験

### 入力因果試験
HDSのFrame変更でミニドラ入力が変わること。

### 記憶因果試験
Prior Memoryの有無・内容変更で検索結果、計算、判断の少なくとも一つが変わること。

### Feedback試験
HDS Feedbackでミニドラ候補が再計算されること。

### Commit権限試験
HDSが拒否した候補がARC世界へ作用しないこと。

### Memory権限試験
HDSが拒否した更新が正本記憶へ反映されないこと。

### Runtime Learning試験
一回目の経験が記憶更新を通じ、二回目以降のFrame・探索・候補・作用を変えること。

### Ablation試験
HDS、ミニドラ、記憶のいずれかを除去した場合に、対応する責任が失われること。

## 14. 完成の見方

AGI三主体統合が完成したと言うためには、単に三moduleが存在するだけでは足りない。

```text
World
→ HDS入力
→ HDS Compiler
→ Prior / Runtime Memory参照
→ Minidora計算
→ HDS Feedback / Commit
→ World作用
→ HDS再観測・因果帰属
→ Memory更新
→ 次回挙動変化
```

この因果循環が実環境で閉じていることを要求する。
