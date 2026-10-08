# 戦略

目的は固定の現行 Learning Machine で ARC-AGI-2 の120課題を完走すること。既存の規則・view・object/relation/action/controlと、その合成を先に調べる。規則の新設自体を成果としない。

必要な未回答課題の観測 → 既存能力の適用・合成 → 全教師の仮説検証 → 最初の不足への最小変更 → input-only確認 → HDS接続 → targeted test → 全回帰 → 同条件の公開評価 → previous/current/delta → 採否を進める。複数の未確定変更を同時に本線へ入れない。HDS v0.4.2、支持・反証・隔離・HOLD・authorityは固定する。

第二回workspace喪失後、外部保存76/107から16件のruntime sourceを当時の完全SHA256に一致させて復旧した。通常CPU失敗を保存したうえで、既存の必要条件証明にborder singleton不在の条件を追加し、改めて89/124、誤出力0、通常資源失敗0、元の107正答格子すべて一致を確認した。これは新たな検証済み復旧であり、失われた92/127 commitやraw履歴の復元とは主張しない。

元の066・072・075/074の完全sourceは未復旧。それぞれを新規再構成として別々に検証・採用し、92/127に到達した。047の既存denial、過去の失敗・HOLD・曖昧性・資源停止・不完全な証拠は維持する。能力・規則数やtest数をARC性能と読み替えない。

詳細と制約は[今回の比較記録](../検証/後半走破/復旧20261007_既存16再検証/README.md)に残す。

最新採用: NEW066の教師適合門・完全経路合成で90/125。前回89/124の124正答格子を全て保持し、誤出力/通常資源失敗0。旧066そのもののsource復元とは区別する。

最新採用:NEW072基準長合成で91/126。前回125格子を全保持、誤出力/通常資源失敗0。元072 sourceの復元とは区別する。

最新採用:NEW075標識二領域の4-action再構成で92/127。126旧格子を全保持、誤出力/通常資源失敗0。以前の92/127と同scoreを再検証したが、以前のcommit/rawや12-action source同一性の復元ではない。残り28課題を既存能力優先で進める。

最新採用:候補121の計数色層旋回で93/128。127旧格子を全保持、誤出力/通常資源失敗0。既存D4動作と新しいcanvas/cue解釈を、空priorの新境界へ同じHDS gateで接続した。残り27課題。

最新採用:候補129の対辺標点の部分key viewで93/129。課題+0、正答格子+1、128旧格子全保持、誤出力/通常資源失敗0。4保持programを残し、2番目のqueryはHOLDのまま。残り27課題。

最新採用:候補134の局所格子側線viewを既存色線反射familyへ接続して94/130。課題+1、正答格子+1、129旧格子全保持、誤出力/通常資源失敗0。strict教師fitとray graphを保持し、残り26課題を既存能力優先で進める。

最新採用:候補142の連結箱参照で94/131。課題+0、正答格子+1、130旧格子全保持、誤出力/通常資源失敗0。元136のCPU失敗を保持し、全footprint外の複数色という必要条件で不可能な所有列挙を避ける。残り26課題。

最新採用:候補150の領域指令・隅cue旋回で95/133。課題+1、正答格子+2、131旧格子全保持、誤出力/通常資源失敗0。元150の失敗cover脱落BLOCKEDと修正audit PASSを区別して保持する。149の回帰timeoutと152の誤出力2/CPU失敗3は非採用のまま履歴へ保存しruntimeに混ぜない。残り25課題。

最新採用:候補156の全panel対辺port連鎖で96/135。課題+1、正答格子+2、133旧格子全保持、誤出力/通常資源失敗0。全適格role・全完成chainの一致とSearchIncomplete伝播を保持し、空priorの通常HDS境界へ接続した。候補151は旧ARC物体端投射のquery0 HOLDで新規最終出力0のため非採用。残り24課題。

最新採用:候補154の矩形継目合成で96/136。課題+0、正答格子+1、135旧格子全保持、誤出力/通常資源失敗0。候補153の固定角矩形配置と候補154の継目一致または全枠条件だけを空priorの通常HDS境界へ接続し、RESOURCE_INCOMPLETEはruntime資源失敗へ伝播する。候補155の資源不足、候補158の完全5候補不一致、候補159の完全3候補不一致、候補157の誤出力1による棄却は非採用履歴に保存し、runtimeへ追加しない。残り24課題。

最新採用:候補164の観測成長合成で96/137。課題+0、正答格子+1、136旧格子全保持、誤出力/通常資源失敗0。凍結済み入力導出の成長系列合成を空priorの通常HDS境界へ接続。全教師再現のkind/versionだけで予測を許可し、教師格子・診断を状態へ保持しない。非有界・複数候補・未完了モデルはHOLD、例外は伝播。元160の監査blocked、162の両query HOLD、161の誤出力1による棄却は非実行履歴へ保存。残り24課題。

最新採用:候補166の折畳帯成長合成で97/138。課題+1、正答格子+1、137旧格子全保持、誤出力/通常資源失敗0。既存164成長familyを凍結166へ置換し、fit契約version3→4を明示。既存19モデル・幾何関数、HDS接続、core、全体gateは保存。全幅・全phaseの一致判定を保持し、未完了・不一致はHOLD。独立監査、native両出力一致、109本の新規実行と保存window29、同一条件120/167の公開評価1回で検証。計数formatterだけの初回失敗と修正後の全回帰を保存。残り23課題。

最新採用:候補167の既存記号命令列内の有限作用合成で98/139。課題+1、正答格子+1、138旧格子全保持、誤出力/通常資源失敗0。凍結167の全4moduleを採用基底166へ統合し、131/135由来の所有視野とtag binding連鎖を含む。D4全9非自明subgroup・全288作用を列挙し、retained失敗・不一致を保存。HDS接続、core、全体gateは不変。独立監査、native両出力一致、109本の新規実行と保存window29、同一条件120/167の公開評価1回で検証。棄却165は誤出力1で不採用、基底に不使用。関連131/135履歴を非runtime証拠として保存。残り22課題。

最新採用:候補177の既存ARC物体端投射内の未観測キー束縛合成で99/140。課題+1、正答格子+1、139旧格子全保持、誤出力/通常資源失敗0。単一の既存特徴モデルで実際に未知キーがある場合だけ、教師から合同peerの全48候補を全教師に照合し、全保持候補と元HDS原理の厳密な不足キー証拠を要求する。元の全既知キー・零/複数モデルは元機構へ委譲し、HDS中核・全体gate・family一覧を保存。遅延fitは教師deepcopyと完了cacheを使用し、失敗を隠さず部分モデルを採用しない。独立124検査、native両出力一致、109本/7839検査の新規実行と保存window29、同一条件120/167の公開評価1回で検証。棄却175は92/130、旧10格子喪失、memory3/CPU5の資源回帰で不採用。175revision1の監査失敗、revision2と176否定結果も非runtime証拠として全て保存。残り21課題。

最新採用:候補179の遮蔽端直角接続で100/141。140旧格子を全保持、誤出力/通常資源失敗0。旧125の完全source復元とは区別した再構成で、既存直線・対辺順序対応で未完了となる二端だけに、同一遮蔽内の一意な前方直角交点を追加した。直角接続は教師から一意に決まる規則ではなく明示した追加prior。全4保持modelの成功・一致を要求し、空priorの通常HDS境界へ接続。独立監査、native一致、targeted8、109本/7839検査の新規回帰と完全一致する保存window29、同条件120/167の公開評価1回で検証。HDS v0.4.2中核・既存consensusは不変。初回nativeの入力配置漏れと最終化templateの未収録report参照失敗を記録し、実装・回帰・score失敗とは区別。現行localへ採用、Git commitは未作成。残り20課題。

最新採用:候補180の空洞種伝播で101/143。141旧格子を全保持、誤出力/通常資源失敗0。既存C4補領域、C8成分、到達グラフ、競合mergeを用い、空洞の物理的境界所有と囲まれた種を合成。遮蔽交差は各witness点の同色fragmentが一意なpairであるという明示した追加priorで、別の点で異なるpairを結び得る。教師から一意に導かれる規則とは主張しない。全4教師再現、空priorの通常HDS境界、独立監査、native両query一致、targeted8、新規109本7839検査と完全保存window29、同条件120/167の公式評価1回で検証。HDS v0.4.2中核・全体gate・既存consensus不変。現行localへ採用、Git commit未作成。残り19課題。

最新採用:候補182の所有間隙軸束縛で102/144。143旧格子を全保持、誤出力/通常資源失敗0。既存最大保持対称剪定内のforeground最大保持tieだけに、全教師で支持された同一C8成分の行内背景間隙の完全対称軸を束縛する。追加priorは教師と整合するが、論理的一意性は主張しない。元のsource軸・最終出力一致・編集量制限を保持し、既存成功tupleは不変。凍結1ファイルのみ変更し、HDS中核・接続・登録・全体gate不変。独立監査、native両query一致と旧q1完全一致、targeted20、既存剪定13、新規109本7839検査と完全保存window29、同条件120/167公式評価1回で検証。候補181は誤出力1・増分0で棄却し、sourceと反証を非runtime履歴として保存。現行localへ採用、Git commit未作成。残り18課題。

最新採用:候補186第1段r2の完全可視実セルfootprint認識で102/145。144旧格子を全保持、誤出力/通常資源失敗0。旧C4矩形候補が存在する入力では旧認識・所有・全返却tupleを保持し、旧候補0の場合だけ観測された完全可視対称shellと中心の実セルmaskを認識する。d35bdbdc q0のみ新規正答、q1は旧格子一致、q2は最初の失敗HOLD継続。clip mask・参照先存在priorを含む第2段は未採用。凍結kernel1ファイルのみ変更、HDS中核・接続・family・全体gate不変。独立監査、native、targeted157、109本7839検査と完全保存window29、同条件120/167公式評価1回で検証。初版r1は対角同色wire接触反例で監査BLOCKED、初回r2回帰の旧renderer pin停止も保持。r2採用版に現在用renderer期待pinだけ同期し、元script11検査を通常実行で確認。現行localへ採用、Git commit pending、残18課題。

最新採用:候補186第2段の境界clip実セル認識・定義済参照joinで103/146。145旧格子全保持、誤出力/通常資源失敗0。旧ownershipが存在する入力の全roleと返却tupleを保持し、旧ownership不能かつ不可避wire複数色、完全C4見本と境界clip物体がある特定域だけを同じ実セルmaskで拡張する。新域の端点接触は描画前に入力key/valueの定義済参照関係でjoinし、全保持候補の成功・一致を要求する。この参照存在priorは教師と整合するが論理的一意性を主張しない。d35bdbdc q2のみ新規正答、q0/q1完全保持。凍結kernel1ファイルのみ変更、HDS中核・接続・family・全体gate不変。現在用fixtureのrenderer期待pinだけ新SHAへ同期し元fixtureと理由を保存、動作assert・期待output・他pin不変。独立監査66、native一致、targeted161、新規109本7839検査と完全保存window29、同条件120/167公式評価1回で検証。既存の監査失敗・棄却履歴を保持。現行local採用、Git commit pending、remote writeなし。残17課題。

最新採用:候補187の遮蔽軌道窓viewを既存二軸欠損補完familyへ接続し104/147。旧146格子全保持、誤出力/通常資源失敗0。元axesの教師fit成立域では新viewをfitせず旧成功・HOLD・全返却tuple・記録を保持する。旧fit不成立域のみ可逆mask色置換とcropを接続し、未観測の矩形折畳軌道を全包含極大局所contextと全donorの一致で束縛する。これは教師と整合する明示的追加priorで、教師から論理的に一意とは主張しない。0934a4d8 q0のみ新規正答。kernel SHA一致、HDS v0.4.2中核・接続・family一覧・全体gate不変。独立pure監査908 synthetic全列挙一致・旧成立297保存・教師4/4、native一致、targeted53、新規109本7839検査＋依存/AST同一の保存window29、同条件120/167公式評価1回で検証。初回targetedは元値と同じ値を代入したfixture不備を保存し、必ず異なる値へ修正してPASS。既存失敗・棄却履歴保持。現行local採用、Git commit pending、remote writeなし。残16課題。

最新採用:候補188の標点巡回を空priorの通常HDS境界へ接続し105/148。旧147格子全保持、誤出力/通常資源失敗0。初panelで矢印と疎標点の所有を確定し、同色unionで一時遮蔽された標点も論理保持しtip到達だけで消費する。全標点消費終端、終端を省いた等間隔snapshot、初期actor所有等は教師整合の明示priorであり論理的一意性は主張しない。全3保持modelの成功・一致を要求し、SearchIncompleteは例外伝播する。5545f144 q0のみ新規正答。旧native全family状態一致・採用済family0を確認しHOLD迂回ではない。kernel凍結一致、HDS v0.4.2中核・全体gate不変。独立監査206、pure targeted52、統合targeted21、native一致、新規109本7839検査＋依存/AST同一の保存window29、同条件120/167公式評価1回で検証。準備時copytree既存directoryとpure fixture証拠path不備は保存し修正。旧147 source未回収HOLDを含む既存失敗・棄却履歴保持。現行local採用、Git commit pending、remote writeなし。残15課題。

最新採用:候補189の受動凡例転写を空priorの通常HDS境界へ接続し106/149。旧148格子全保持、誤出力/通常資源失敗0。現存初期probeのC8 glyph・二色key/value・同時clipped stampを再利用し、部分所有と背景識別、非干渉の受動セル保存を合成。全4教師fitした3背景modelを全保持し、保持候補の失敗/不一致はHOLD、未知例外は伝播する。受動セル保存は教師整合の明示priorであり論理的一意性は主張しない。消去対案も全教師fitしqueryで7セル異なるHOLD案として保持。旧完全parserのHOLDと127/128 source未回収を保存し、復元とは主張しない。abc82100 q0のみ新規正答。旧native94 family状態一致・採用済family0を確認しHOLD迂回ではない。kernel凍結一致、HDS v0.4.2中核・全体gate不変。独立監査34、pure targeted128、統合targeted22、native一致、新規109本7839検査＋依存/AST同一の保存window29、同条件120/167公式評価1回で検証。既存失敗・棄却履歴保持。現行local採用、Git commit pending、remote writeなし。残14課題。

最新採用:候補191r3の完全矩形物理片不可分viewを既存ARC矩形継目familyへ接続し107/150。旧149格子全保持、誤出力/通常資源失敗0。旧153/154に構造roleがある入力では全返却tuple・HOLD・RESOURCEを保持し、roleなしだけ新viewへ進む。完全矩形mixed-C8成分と矩形leaf不可分は教師整合の追加priorで、論理的一意性とは主張しない。旧13片3出力HOLDを保存し、物理12片の完全seam列挙1出力で446ef5d2 q0が新規正答、q1旧tuple保持。r1の全回帰資源失敗を保存。r2の無条件fit必要条件案は旧域RESOURCEを変えるため棄却し、r3は旧域を先に保持して新域のみ教師renderer不変量の不可能証明で列挙を省く。全教師を評価し資源失敗を伝播。矩形回帰fixtureはmock対象だけ現apiへ変更、旧kernel検査/assert/期待output不変。純粋33・統合23・独立初版35/r3 42、native一致、新規109本7839検査＋依存/AST同一window29、同条件120/167公式1回で検証。候補190の全対称tie不一致HOLDと全既存失敗履歴を非runtime証拠として保持。HDS v0.4.2中核・全体gate不変。現行local採用、Git commit pending、remote writeなし。残13課題。

最新採用:候補192r2の直交領域所有を空priorの通常HDS境界へ接続し108/152。旧150格子全保持、誤出力/資源失敗0。二色主領域を単位編集費と単位直交曲がり費、沿辺3セル多数外挿priorで復元し、所有差分から消去と8近傍輪郭を同時決定する。これらは教師整合の追加priorで論理的一意性は主張しない。全role保持、候補失敗/不一致HOLD、SearchIncomplete伝播を保持。r1の浮動小数MILP整数性gate欠落は監査BLOCKED、r2で整数性/dual/gapを検証し例外伝播。旧068/122未回収履歴を保持し復元とは主張しない。新依存NumPy2.3.5/SciPy1.17.0を宣言。author初回pure測定のOPENBLAS_NUM_THREADS=1未記載が判明し、既定envではoptimize import中CPU10秒失敗を保存。親承認で両baseline/currentに同じOPENBLAS1を明示、CPU10/512MiB/wall60不変の公式比較を各1回実行。基底107/150全旧出力一致を再確認後、71e489b6両queryが増分。以前の無設定実績と同条件だったとは主張しない。独立r2監査、pure56/統合17/native一致、新規109本7839検査＋依存/AST同一window29。HDS中核・通常gate不変。必要起動契約はRUNTIME.md、ユーザー環境動作は未検証。現行local採用、Git commit pending、remote writeなし。残12課題。

最新採用:候補194の局所軌条鎖所有を空priorの通常HDS境界へ接続し109/154。旧152格子全保持、誤出力/資源失敗0。既存単色C8成分を局所のrail/chain複合所有と前方障害物profileへ合成し、同じ色の異なる物体役割を分離する。最近傍対象、近側輪郭、単位補間、鎖セル数のclip前保存と終端後対角継続は教師整合の明示priorで、論理的一意性を主張しない。全4保持modelの成功・一致、全所有失敗HOLD、例外伝播、strict teacherlist/min2unique/pairdict/bothvalid guardを保持。旧143/149/152完全source未回収と149timeout・152wrong2/CPU3棄却を保持し復元とは主張しない。旧96 family状態・記録同一を確認し88bcf3b4両queryが増分。独立pure/adapter監査PASS、pure163 metamorphic、統合37、native一致、新規109本7839検査＋依存/AST同一window29。同条件OPENBLAS1/CPU10/512MiB/wall60の公式候補1回。193接触経路はwrong1・増分0棄却として非runtime履歴を同梱。HDS中核・通常gate・依存起動契約不変。現行local採用、Git commit pending、remote writeなし。残11課題。

最新採用:候補195の境界表穴転写を空priorの通常HDS境界へ接続し110/155。旧154格子全保持、誤出力/資源失敗0。既存mixed C8矩形表・単色C8物体・C4補領域穴・同時mergeを合成し、canvas端に近いlaneをkeyとして束縛する。これは教師整合の明示priorで、教師からの論理的一意性を主張しない。全表・最小距離同率laneを保持し、一候補でも失敗/不一致ならHOLD、例外伝播。strict教師list/min2全unique/pairdict/両grid valid/同shape、fit返却modelのみ状態を保持。旧137/161完全source未回収・161wrong1棄却を保持し復元とは主張しない。旧97 family状態・記録同一を確認しdbff022c q0が増分。独立pure/adapter監査PASS、pure44、統合34、native一致、新規109本7839検査＋依存/AST同一window29。同条件OPENBLAS1/CPU10/512MiB/wall60の公式候補1回。HDS中核・通常gate・依存起動契約不変。現行local採用、Git commit pending、remote writeなし。残10課題。

最新採用:候補196r2の多面欠損所有を空priorの通常HDS境界へ接続し111/156。旧155格子全保持、誤出力/資源失敗0。既存192の二色unique_regionを各surfaceに適用し、欠損marker・対面色輪郭・余剰消去を同時合成。独立最小面所有は教師整合の明示priorで、論理的一意性を主張しない。全保持model成功/一致、所有重複・輪郭競合・余剰競合HOLD、数値/資源例外伝播を維持。strict教師guardとfit modelのみstate。旧138/165完全source未回収と165wrong1棄却を保持し復元とは主張しない。旧98 family/全記録一致、de809cff q0が増分。r1 nativeのHiGHS仮想メモリ予約によるmemory_limit、gc/trim/cache診断失敗を保持。r2は共有192のmilp実行option threads=1だけ変更し、目的/制約/gap/許容/数値gateは不変。旧192全5入力の出力/数値証明一致、独立fault15・教師/転置監査PASS。SciPyの転送warningは隠さずRUNTIMEへ記載。純粋核凍結一致、統合33/native一致、新規109本7839＋依存/AST同一window29。OPENBLAS1/CPU10/512MiB/wall60で公式候補1回。HDS中核・通常gate不変。現行local採用、Git commit pending、remote writeなし。残9課題。

最新採用:候補198の凡例所有境界viewを既存標識移動family内へ接続し112/157。旧156格子全保持、誤出力/資源失敗0。旧parser全role不能域だけ回収171r2の局所凡例・囲み所有と斜行両直交中間footprintの所有包含を合成。中間標点占有を壁にせず、旧block/transparentを全4model保持。これは教師整合の明示priorで、論理的一意性を主張しない。旧新fit全model集合一致、strict教師guard、新stateはmodelのみ。旧roleが1つでも成立するqueryは成功/HOLD/全tupleを完全保存し、新域も全保持候補成功/一致と例外伝播を維持。新familyなし、HDS中核・通常gate・既存核・HiGHS threads=1不変。旧99family/全記録一致、q1全返却保持、88e364bc q0だけ新規正答。171wrong1、174診断、198初案HOLD、197全候補不一致HOLDを非runtime保存。独立pure/adapter監査PASS、pure162・統合25・旧093回帰16/native一致、新規109本7839＋依存/AST同一window29。OPENBLAS1/CPU10/512MiB/wall60で公式候補1回。初回manifest確認assertとpure report schema誤認はharness履歴へ保存、runtime再実行なし。現行local採用、Git commit pending、remote writeなし。残8課題。

最新採用:候補200の小物体優先・元位置順副キー合成で113/158。旧157格子全保持、誤出力/資源失敗0。旧act成功の全tupleと他failureを保持し、small_firstの等セル数異色競合だけ既存source_firstの元bbox辞書順を合成。教師整合の明示追加priorで論理的一意性は主張しない。旧4model全保持、全role/program成功・完全一致と例外伝播を保持。99family/全教師記録同一、q0全返却保持、247ef758 q1だけ新規正答。kernel1file変更、HDS中核・接続・教材・通常gate・HiGHS threads=1不変。旧回帰pin停止と元fixtureを保持し、親承認のEXPECTED_CORE一行だけ同期、assert/output/他pin不変。独立12000 action/旧成功3600保存、pure2400、統合21、旧17/native一致、新規109本7839＋依存/AST同一window29。OPENBLAS1/CPU10/512MiB/wall60で公式候補1回。targeted初回tuple対JSON list比較不備を保存し正規化だけ修正。199HOLDを非runtime履歴に保存。現行local採用、Git commit pending、remote writeなし。残7課題。

最新採用:候補213: 113/158 → 115/160（+2課題/+2格子）。旧158格子全保持、誤出力0・通常資源失敗0。監査済み209/210の4moduleをbytes不変で合成し、通常HDS登録8行のみ追加。7b80bb43・3dc255dbを新規正答。208r2は候補211の誤出力によりfamily全体を棄却し、faa9f03dはHOLDへ復帰。予測の評価後修正・model部分選別なし。旧99family全記録保持。新規109本7839検査＋同一AST/依存window29を合成した110本7868検査PASS。OPENBLAS1/CPU10/512MiB/wall60/3worker、HiGHS threads=1不変、公式候補1回・基底再採点なし。204–207 HOLD、208r1監査block、209旧routing案とREADME query出力prose露出、210の全回帰harness誤cap失敗、211全負結果、212既存能力のみ増分0を保存。現行local採用、Git commit pending、remote writeなし。残5課題。

最新採用:候補214: 115/160 → 116/161（+1課題/+1格子）。旧160格子全保持、誤出力0・通常資源失敗0。faa9f03d新規正答。既存208r2幾何を再利用し、入力で観測した経路層関係と標識に基づく反転を修復後交差へ伝播。旧長さ優先描画は不採用。3moduleと通常HDS登録4行のみ追加。2標識経路の新交差を扱えないv1監査blockを保存し、実出力交差HOLD guardの最小修正後に独立130検査PASS。旧101family/metadata保持、pure教師4/4・400検査、adapter599検査、120 sanitized tasks scope確認。新規109本7839検査＋同一AST/依存window29を合成した110本7868検査PASS。公式候補1回・基底再採点なし、通常条件不変、予測の評価後修正なし。215長軸候補はHOLDで非runtime履歴に保存。現行local採用、Git commit pending、remote writeなし。残4課題。

最新採用:候補217: 116/161 → 117/163（+1課題/+2格子）。旧161格子全保持、誤出力0・通常資源失敗0。581f7754の2query新規正答。C8 cavity enclosure特徴からcue基準残差移動を教師で導出、crop-before-render、全role合意と衝突HOLD。旧102family全記録保持、2moduleと通常HDS登録のみ追加。初期same-color衝突監査block、409aa875のMemoryError、必要教師histogram保存precondition修正、初回pure import harness失敗と旧pin回帰を全保存。修正後scope120、独立production監査、native一致、最終pin新規109本7839＋同一AST/依存window29で110本7868検査PASS。公式候補1回・基底再採点なし、通常資源条件不変。216 no-hidden refutation・218 order-sensitivity HOLD・220 frozen未採点候補は非runtime履歴に保存。219未採点runtimeは不採用。現行local採用、Git commit pending、remote writeなし。残3課題。

最新採用:候補221: 117/163 → 118/165（+1課題/+2格子）。旧163格子全保持、誤出力0・通常資源失敗0。e12f9a14の2query新規正答。既存190 rendererをbytes不変で再利用し、有限例外/default continuation priorを通常HDSへ結合。明示priorは教師唯一ではなく、高い過適合リスクを残す。例外cardinality3はnegative port観測1件のみで、native support3を3独立negativeと読み替えない。raw220 unknown-HOLD競合モデルと218 order-sensitivity失敗を保持。旧103family全記録保持、2moduleと通常HDS登録のみ追加。24教師順序とstrict guards監査、native一致、scope120、最終pin新規109本7839＋同一AST/依存window29で110本7868検査PASS。公式候補1回・基底再採点なし、通常資源条件不変。219は117/163増分0・wrong1のため全candidate棄却、実際の全文公式結果・lazy/slot修正/資源履歴を非runtime保存。現行local採用、Git commit pending、remote writeなし。残2課題。

最新採用:候補222: 118/165 → 119/166（+1課題/+1格子）。旧165格子全保持、誤出力0・通常資源失敗0。a6f40cea新規正答。既存frame role/continuous rendererを再利用し、周期相対row/column residueと教師由来correctionを通常HDSへ接続。parity有限例外/default continuationは教師唯一でなく、未知raw context HOLDと区別する明示prior。59 hidden perimeter pixelは3教師由来の相関観測、8 correction pixelは1frame由来で独立59例と扱わない。D4は変換教師で再学習後の同変性。旧104family全記録保持、3moduleと通常HDS登録のみ追加。strict guards/監査、native一致、scope120、最終pin新規109本7839＋同一AST/依存window29で110本7868検査PASS。公式候補1回・基底再採点なし、通常資源条件不変。223固定点診断は全教師/queryで最小最大解同一のHOLD/増分0。query0不動、compound query1移動の訂正説明を保存。224未採点runtimeは不採用。現行local採用、Git commit pending、remote writeなし。残1課題。

最新採用:候補224: 119/166 → 120/167（+1課題/+1格子）。対象120/120課題・167/167例を完全正答、残0課題。旧166格子全保持、誤出力0・通常資源失敗0。b6f77b65のcompound query1新規正答。既存173 union/deletionと単一制御経路を保持し、unique compound解釈の可視材default/有限例外priorを通常HDSへ接続。44post観測、最大8length/256mapping、全教師全mapping評価、未完了探索は全体abort。支持構造教材1fileと2companionのみ変更、旧105family全記録とsingleton全tuple保持。監査でquarantine/既知key HOLD/衝突/資源未完了/slot境界を確認し、評価後予測変更なし。初回回帰BLAS1未設定の108PASS/1資源失敗、同条件224/119対照、numpy/OpenBLAS診断、同じ元CPU10秒/512MiBでBLAS1復旧を区別して全保存。最終fresh109本7839検査はOPENBLAS1/OMP1で成功、同一AST/依存window29合成110本7868検査PASS。公式候補1回は従来OPENBLAS1/OMP未設定/CPU10秒/512MiB/wall60で完了、基底再採点なし。225は教師限定・未採点、目標到達により不要な非runtime履歴。現行local採用、Git commit pending、remote writeなし。ユーザー環境動作、main適用/commitは未確認。
