<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/planning/pyinto_migration.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# pyinto 新アーキテクチャ・名称体系・移行対応表

- **基準**：henkan 第35回成果物（2026年10月12日）と、2026年10月13日までの設計議論。
- **位置付け**：第36回の準備として作成した**新設計と移行計画の文書**。現行コードの仕様正本ではない。
- **実装状態**：この文書の追加時点で、配布名・import・型・API・Targetの配置は旧henkanのままである。
- **対象範囲**：名称、論理的な所属、既存実装との対応、変更順序。新規Construct・Python記法・意味契約の追加は扱わない。

「採用」は設計上の用語・方針が決まったことを指し、「実装済み」や「リポジトリ分割済み」を意味しない。

## 1. 確定済みの設計方針

- **プロジェクトの正式名称は `pyinto`**。旧名称 `henkan` と、旧実現側候補 `taiou` は新しい公開体系では使わない。
- **Host** は `pyinto` 本体リポジトリの分類名。Surface、Foundation、Language Interface、Python Source Adapter を**一つのリポジトリで**管理する。論理的責務が異なるからといって、独立リポジトリを増やさない。
- **Interface** は、具体的なConstruct群とそれらの意味契約を定義するまとまり。言語構造を表す要素は **Language Construct** と呼ぶ。Modelはこれらの公開上の抽象面であり、個別Targetの実装を含まない。
- **Target** は出力先の言語・環境。**Target Implementation** はその実装を指す総称であり、基本言語構造向けは **Language Implementation**、外部抽象Interface向けは **Interface Implementation** と呼び分ける。個々の実現規則は **Realization**。
- 基本言語Targetの配布リポジトリ名は **`pyinto-target-<language>`** とする。最初は `pyinto` と `pyinto-target-c` を管理対象とし、**物理的なリポジトリ分割は後工程**とする。
- 旧Python Targetは**非公開の開発用Python Realizer**としてHostと同じリポジトリに保持する。公開Targetとしての独立配布も、通常のSurfaceへの暗黙接続も行わない。
- 既存のConstruct・Admission・Realization・Frontendを設計し直すことは目的にしない。Python構造および外部関数・ライブラリのModel化を、第35回までの意味契約を保持したまま扱う。

**今回の移行の評価軸は「意味保存・拒否の維持」と「公開語と実装の対応が説明可能なこと」**である。名前だけの置換を機能変更として扱わない。

## 2. 公開用語の定義と境界

| 用語 | 意味・範囲 | 採用状態 |
|---|---|---|
| **pyinto** | プロジェクト・Hostリポジトリ・将来の配布名 | 採用、未移行 |
| **Host** | Surface / Foundation / Language Interface / Python Source Adapterを同居させる本体の分類 | 採用 |
| **Surface** | 変換要求を受けるAPI・将来のCLIという役割 | 役割名を維持。CLIの実装済みを意味しない |
| **Foundation** | Construct基盤、Admission、Realization登録・合成などの共通機構という役割 | 役割名を維持。別パッケージを新設しない |
| **Model** | Interfaceに定義された構造・操作・契約をTarget非依存に扱う抽象面 | 定義を整理 |
| **Interface** | Constructと意味契約の所有・公開単位。Python外部関数・ライブラリの抽象化も含む | 採用 |
| **Language Construct** | `Branch`、`While`、`Arithmetic`等の言語構造を表す具体的なConstruct | 採用。汎用基底クラス`Construct`は改名しない |
| **Python Source Adapter** | Pythonの構文・型・参照をModel化する役割 | 役割名。実装クラス`PythonFrontend`は維持 |
| **Target** | C、Rust等の出力先言語・環境の一般名 | 採用 |
| **Target Implementation** | Targetごとの実装全般の総称 | 採用。新たな基底型を必須にしない |
| **Language Implementation** | Language ConstructをあるTargetで実現する実装 | 採用 |
| **Interface Implementation** | 外部InterfaceをあるTargetで実現する実装 | 採用 |
| **Realization** | 特定Construct等をTargetで実現する規則。生成済みソースそのものではない | 採用 |
| **Composition / Rendering** | 実現結果の合成 / 生成コードへの描画 | 維持 |
| **Bundle** | 複数コンポーネントを組み合わせる公開単位 | 暫定呼称。実装・配布方式は未決定 |

**用語の区別**：`Interface` は意味の定義であり、Pythonの呼び出しをそれへ結び付ける **Interface Mapping** は対応付け機構である。`Target` と `Target Implementation`、`Realization` と生成ソースも区別する。

**非目標**：`Model.language.While` のような新しい名前空間APIの即時導入、複数のPythonFrontendの交換機構、任意分野の未知の抽象化要件の先行設計、Targetの自動探索機構。

## 3. 論理構成と依存方向

```text
pyinto（Host、当面は単一リポジトリ）
  Surface            変換要求受付、入口API（CLIは将来）
  Foundation         Construct / Admission / Composition等の共通機構
  Language Interface 既存の言語構造Constructと意味契約
  Python Source Adapter  PythonFrontend、Portによる外部APIの正規化等
  tests/support      非公開の開発用Python Realizer（配置は未確定）

外部の独立管理対象
  pyinto-target-c   CのLanguage Implementation
  将来のTarget Implementation（必要に応じて）
  将来の抽象Interface・Interface Implementation（必要に応じて）
```

- Hostは特定Target Implementationを固定的にimport・自動選択しない。Target ImplementationはHostの**公開されたModel・Admission・Realization用API**のみ参照する。
- `pyinto-target-c` はリポジトリ名の採用例だが、**現行実装の `src/henkan/targets/c/` はこの時点では未移動**。
- 複数のInterfaceやTarget Implementationを組み合わせた公開単位は将来の検討対象であり、今からBundleリポジトリを作る必要はない。
- 旧Python Packは第35回までの検証資産として保持し、意味保存・再正規化の実行テストへ活用する。公開Targetと同等の対応範囲を完了条件にしない。
- 既存のLanguage Constructの契約・Frontend受理/拒否条件・未対応Realizationの明示的拒否を、名称変更のために変更しない。

## 4. 現行実装と新しい用語・所有関係の対応表

次表は**現在のファイルと、将来の概念上の所属・変更判断**を対応付けたもの。将来の正確な配置・シンボル名を、推測で既成事実にはしない。

| 現在の場所・識別子 | 概念上の所属 | 今回の判断 | 変更するときの注意 |
|---|---|---|---|
| `pyproject.toml`、`src/henkan/`、`henkan` import | Hostの配布ID | **改名確定**：`pyinto` | パッケージ走査・Contrace対象・例・テストと一緒に更新 |
| `src/henkan/api.py`、`convert()` / `realize()` | Surface | **API名維持**、名前空間のみ移行 | `bindings`、`ports`等の引数名は別工程で評価 |
| `src/henkan/__init__.py` | Surface公開入口 | 名前空間のみ移行 | Exportと互換性方針を追跡 |
| `src/henkan/constructs/base.py` の`Construct`、`Value` | Foundation / Language Interface | **識別子維持** | 汎用基底を`LanguageConstruct`へ置換しない |
| `src/henkan/constructs/types.py` の`ValueType`、`Symbol`等 | Language Interface中心 | **原則維持** | `PortType`、`PORT_OBJECT`は別の意味境界がある |
| `src/henkan/admission.py` の`AdmissionRule`、`AdmissionDeclaration`、`AdmissionRegistry` | Foundation | **名称維持** | Contractの検査と意味保存の実証を混同しない |
| `src/henkan/constructs/admission.py` の`CORE_ADMISSION` | Language Interfaceの契約集合 | **改名対象**：`LANGUAGE_ADMISSION`（推奨） | 拒否・上書き防止を維持。定数名だけでなく既定値参照がある |
| `AdmissionRegistry.require_core()` | Foundationの必須契約チェック | **連動検討**：意味上は基準カタログの保持検証 | 新API名は実装段階で確定。検査を削除しない |
| `src/henkan/constructs/`の`control.py`、`operations.py`等 | Language Interface | **Construct名維持** | 77種類の意味と既存仕様IDを保持 |
| `src/henkan/frontend/`、`PythonFrontend` | Python Source Adapter | **名称維持**、名前空間のみ移行 | Source Adapterの交換機構を新設しない |
| `src/henkan/intrinsics.py`、`IntrinsicRegistry` | Python側標準操作の正規化 | **名称維持** | 型付き基本操作と外部Interfaceの関係は説明上区別 |
| `src/henkan/ports/registry.py` の`PortRegistry` | Python Source AdapterのInterface Mapping | **改名対象**：`InterfaceMappingRegistry`（推奨） | `InterfaceRegistry`への単純置換をしない |
| `PortDefinition` / `PortClassDefinition` / `PortMethodDefinition` | Python側のInterface Mapping定義 | **改名対象**（個別名は未確定） | 関数、クラス、メソッドの対応付けを混同しない |
| `src/henkan/frontend/ports.py` の`PortNormalizer` | Python Source Adapterの正規化 | **改名対象**（個別名は未確定） | 登録済み外部APIの受理・拒否が変わらないこと |
| `PortType` / `Symbol.port_type` / `ValueKind.PORT_OBJECT` | 外部オブジェクトのModel上の型 | **判断保留**：機械的改名は禁止 | 型同一性・登録キー・Target型表記を保持 |
| `src/henkan/bindings/registry.py` の`BindingRegistry` | FoundationのRealization登録とTarget固有設定 | **改名対象**：`RealizationRegistry`（第一候補） | 型表記・識別子管理も担うため名称と責務を確認 |
| `src/henkan/bindings/`（`registry.py`、`call_layout.py`、`regulation.py`等） | Foundation / Language Interfaceの合成処理 | **パッケージ名改名を検討** | 相互importと多数のテスト参照がある。先に機能分割しない |
| `Composer`、`EmitContext`、`Template`、`Slot`、`Layout`、`Renderer` | Composition / Rendering | **名称維持** | `pack_target`等のPack構成DSLは別の責務として維持 |
| `src/henkan/bindings/c.py` | HostからC Targetへの互換参照 | **境界整理対象** | Host → Cの静的importを最終的に無くす |
| `src/henkan/targets/c/pack.py` の`CTargetPack`、`c_bindings()` | C Language Implementation | **公開クラス名改名を検討** | `Target Implementation`は分類名。`pack_*` DSLは保留 |
| `src/henkan/targets/python/pack.py` の`PythonTargetPack` | 開発用Python Realizer | **公開対象から除外**、内部名・配置は未確定 | `python_bindings()`に依存する既存テストを保全 |
| `src/henkan/contracts/` | Contraceによる開発検証資産 | **現行名称維持** | ここでのContractとModelの意味契約は別物 |
| `examples/`、`tests/` | 回帰・公開例 | **参照名の移行対象** | C Target統合テストと内部Python Realizerテストを分類 |
| `scripts/docs.py` | 文書生成・整合性 | **追従対象** | 生成Markdownを直接編集しない |
| `devdocs/canonical_sources/vocabulary/canonical.py` | 用語正本 | **新用語へ更新対象** | 現行GLOSSARYはまだ旧用語。`test_public_identity.py`の前提に注意 |
| `devdocs/canonical_sources/specification/` | 現行の仕様正本 | **実装と同時に更新** | `CST/FRT/CMP/CVT` IDは維持 |
| `devdocs/canonical_sources/readme/`、`status/` | 公開説明・開発状況の正本 | **実装が揃った後に更新** | 第35回で成立するAPIを新APIとして先取りしない |
| `devdocs/canonical_sources/changelog/` | 履歴の正本 | **履歴は書き換えない** | 変更が成立した時点で新しい移行履歴を追加 |

**注意点1**：`bindings/registry.py` は `Program` / `Call` / `Symbol` / `CORE_ADMISSION` を参照し、レシピ登録のほか型表記、識別子規則、生成要件も保持する。単なる「登録だけ」のレジストリとして改名・分割しない。

**注意点2**：`ports/registry.py` は`CORE_ADMISSION.extend(...)`を用い、`PortType`は`Symbol`の型やTargetの型名選択にも使われる。Portの概念整理とPython側Mappingの改名、Model内部の型キーの改名は**別の変更単位**である。

**注意点3**：`bindings/c.py`は`henkan.targets.c.pack`を再エクスポートする。リポジトリが一つの段階でも、この依存方向は最終分離の阻害要因として監査する。

## 5. 参照影響の静的調査結果

**調査方法**：第35回ZIPの `src/henkan/`、`tests/`、`devdocs/canonical_sources/`、`examples/`、`scripts/` に含まれる`.py`を文字列・正規表現で走査。出現数はコメントやdocstringも含み、**改名が必要な件数を意味しない**。生成済みMarkdownは正本に基づいて再生成するため、この集計から除外した。

| 検索群 | 実装：件数/ファイル | テスト：件数/ファイル | 正本ソース：件数/ファイル | 例：件数/ファイル |
|---|---:|---:|---:|---:|
| `henkan` | 83 / 39 | 429 / 74 | 37 / 8 | 26 / 10 |
| `Binding*` または `bindings` | 100 / 22 | 348 / 52 | 61 / 8 | 15 / 5 |
| `Port*`、`ports`、`port_type`、`PORT_OBJECT` | 211 / 26 | 103 / 28 | 108 / 9 | 33 / 9 |
| `CORE_ADMISSION` | 8 / 3 | 45 / 15 | 0 / 0 | 0 / 0 |
| `*TargetPack` または `Target Pack` | 17 / 9 | 3 / 2 | 30 / 7 | 1 / 1 |

`scripts/docs.py`には`henkan`への固定参照が3件あり、生成する仕様INDEXのタイトルや一時ディレクトリ名にも旧名称が含まれる。`pyproject.toml`には配布IDに加えContrace走査対象のモジュール名が列挙されている。

**影響の評価**：プロジェクト名は全体に広いが機械的に追跡しやすい。BindingとPortは実装・テスト・文書へ広く浸透しているため段階を分ける。`CORE_ADMISSION`は件数こそ小さいが契約受理の安全性に直結する。TargetPackは数が少なくても独立配布境界と関係する。

## 6. 移行の実施順序と検証ゲート

**この文書を追加する作業では第1工程と第2工程だけを行う。** 第3工程以降は別の実装作業として扱い、各段階でテスト・仕様を揃える。

| 工程 | 内容 | 変更単位とゲート |
|---|---|---|
| **1：設計文書（今回）** | 公開用語、Host/Targetの責務、Python Realizer方針を明記 | 本書を正本ソースから生成。既存GLOSSARY/仕様と将来設計を明示的に区別 |
| **2：改名監査（今回）** | 現行コード/文書との対応、改名と維持・保留の区分、影響規模を固定 | 本書の対応表・静的集計が成果物。実装シンボルは未変更 |
| **3：配布名・名前空間** | `henkan`→`pyinto`の独立変更 | `pyproject.toml`、import、Contrace、例・テスト、文書のAPI表記を同時更新して全試験成功 |
| **4a：Admission関連** | `CORE_ADMISSION`の所有名と関連APIを整理 | 契約宣言数、既定Admission、置換・未登録の拒否を維持 |
| **4b：Binding関連** | 公開`BindingRegistry`と旧`bindings`呼称を整理 | 型表記・識別子・Contract検査・Template/Slot合成の動作を維持 |
| **4c：Port関連** | まずPythonのMapping名、次に必要なら外部オブジェクト型関連名を扱う | import・関数・クラス・メソッド・属性・型・競合拒否を維持。単純置換しない |
| **5：Host/Targetの論理境界** | C TargetのHostからの逆向きimport等を整理 | 同一リポジトリのまま、C側だけがHostの公開APIへ依存することを検査 |
| **6：開発用Python Realizer** | テスト資産として配置・利用を整理 | Surfaceの通常利用からの非依存と、意味保存検査用の動作を維持 |
| **7：公開文書の最終反映** | README、STATUS、GLOSSARY、仕様正本を実装済み状態へ合わせる | `canonical_sources`のみ編集し、生成・整合性・仕様ID/履歴を検証 |
| **8：配布分離の準備** | `pyinto-target-c`の独立ビルド・依存・適用を検証 | 単独Wheel、Host単体の動作、別環境での接続、拒否系の継続を確認 |

**仕様更新の扱い**：工程3〜6で現行仕様が参照するAPIの名前・配置が変わる場合、対応する`CST`/`FRT`/`CMP`/`CVT`正本ソースを**その工程内で**更新する。工程7は整理・照合の最終工程であり、仕様変更をまとめて遅らせる意味ではない。

**CHANGELOG**：旧名称が使われていた開発履歴は書き換えず、新名称の実装が成立した工程ごとに移行履歴を追加する。

**API互換性**：現在Alphaで後方互換性は保証されていないが、旧APIの削除と互換層の有無は実装工程で明示する。意図しない互換レイヤーを永久に増やさない。

## 7. 実装移行時の注意点

- **仕様の先取り**：設計名称が確定しても現行実装は旧API。`GLOSSARY.md`などの現行用語正本は、関連テスト（`test_public_identity.py`）と一緒に後続工程で更新する。本書を現行仕様の代替にしない。
- **Portの二重性**：Source側の対応付けとModel側の外部オブジェクト型は別。`Interface`という語だけに機械的統合しない。
- **Bindingの役割の広さ**：`BindingRegistry`は登録だけではなく型表記等を持つ。`RealizationRegistry`という名は第一候補だが、実装変更時に公開API全体との整合を確認する。
- **Target分離**：`bindings/c.py`はC Packへ逆向きに依存している。対象外のC生成・テストを失わないよう、参照の移行とビルド検査を別工程で行う。
- **意味契約**：`supports`は照合のための宣言であり、実行意味の証明ではない。名前の変更を根拠に受理範囲を広げず、実行テストで検証する。
- **Language Constructの同名Symbol**：第35回引継の同名・異型Symbol問題は未確定の検証課題。新たなFrontend禁止規則を先行導入しない。
- **工程境界**：論理的な役割の名前と、実際のパッケージ配置を混同しない。リポジトリ分割は**今回行わない**。

## 8. 完了条件と検証コマンド

第35回成果物を基準に、後続工程では以下を繰り返す。

```bash
python -m pytest -q
ruff check .
ruff format --check .
basedpyright
python scripts/docs.py render
python scripts/docs.py check
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

- **第1〜2工程の完了条件**：本書の正本ソースと生成文書が一致し、旧仕様・旧API・旧テストが変更されず、文書生成・チェックと既存テストが成功すること。
- **工程3〜4の完了条件**：公開名・コード・仕様・テストが対応し、予期しない受理範囲の変化がないこと。
- **工程5〜6の完了条件**：HostのTarget非依存、内部Python Realizerの非公開性、C Targetの独立接続、明示拒否の保持を確認すること。
- **分割着手の条件**：C Targetを別配布物として組み立てる際、内部モジュールへの依存が解消され、利用者が公開APIだけで接続できることを確認すること。

## 9. 第36回：工程3（配布名・名前空間）の結果

- **実施済み**：配布名を`pyinto`へ変更し、`src/pyinto/`のimport、テスト、例、Contrace走査設定を追従させた。例のアダプタパッケージ名も`demo_*_pyinto`へ変更した。
- **現行API**：`pyinto.convert()`、`pyinto.realize()`を提供する。引数名や`BindingRegistry`、`PortRegistry`、`CORE_ADMISSION`、Target Packの識別子は**まだ従来どおり**。
- **変更なし**：現行のC/Python Pack配置、意味契約、Frontend受理・拒否条件、Shikumi宣言名。C Targetの独立配布は未実施。
- **履歴の扱い**：§4〜5の`henkan`参照と件数は、移行前の監査スナップショットとして残す。旧CHANGELOGの名称も当時の開発履歴として残す。
- **内部生成名**：`__henkan_lambda_N`は名前衝突の回帰試験と監査記録があるため、この工程では変更しない。

**次の工程**：`CORE_ADMISSION`の契約登録名の整理（工程4a）。現行仕様と実装を対応させて変更する。

## 10. 第36回：工程4a（Admission名称）の結果

- **実施済み（工程4a）**：Language Constructの既定契約台帳を`LANGUAGE_ADMISSION`に改名し、収録する型の一覧を`LANGUAGE_CONSTRUCT_NAMES`に改名した。いずれも`pyinto.constructs.admission`内の名称変更であり、所有関係・意味契約の新設は行わない。
- **汎用API**：`AdmissionRegistry.require_core(core)`は`require_baseline(baseline)`に改名した。これは引数で与えた任意の基準台帳の宣言が、検査対象の台帳内で削除・置換されていないことを確認する処理であり、Language Construct固有のAPIではない。
- **既定接続**：`EmitContext` / `Composer`と`PortRegistry`の既定契約台帳は引き続きLanguage Constructの登録一式を含む。外部Constructは明示宣言による`extend()`を必要とし、未登録Construct・未宣言supportsは従来どおり拒否する。
- **互換性**：Alpha段階の内部API整理として、旧`CORE_ADMISSION` / `require_core()`の別名は設けない。第35回からの履歴、工程3当時の旧識別子に関する記録は、その時点の事実として残す。
- **適用範囲**：実装とテスト、現行仕様CMP_018、本移行計画の実施記録とCHANGELOGを更新。`BindingRegistry` / `PortRegistry`およびShikumiの宣言名は変更しない。

**次の工程**：工程4b（Binding関連の公開API名と内部の責務の整合確認）。工程4aの終了は、後続工程の自動完了を意味しない。

## 11. 第36回：工程4b（Realization名称）の結果

- **実施済み（工程4b）**：`BindingRegistry`を`RealizationRegistry`、`src/pyinto/bindings/`を`src/pyinto/realizations/`に変更。旧`bindings/realization.py`が保持していたLayout/Rendererは`realizations/layout.py`として配置した。型表記・名前規則・ヘッダー・Recipe・Admission契約照合の機構は継続利用する。
- **公開API**：`pyinto.convert(..., realizations=...)`と`pyinto.realize(..., realizations=...)`に統一。`EmitContext`は`registry`を参照する。旧キーワード・旧クラス・旧モジュールの互換別名は設けない。
- **第37回第5工程で変更した点**：旧記述器と互換機構はすべて廃止済み。この節の一部は第36回時点の判断記録として残す。
- **当時維持した名前**：Shikumiの`binds`（呼出登録DSL）、`c_bindings()`・`python_bindings()`・デモの`*_bindings()`（Target別factory）、`PortRegistry`等（工程4c対象）、Python変数の通常のbinding。Target factoryとTargetPackの整理は今後の工程で行う。
- **責務**：Target Implementationの分類・実体の分離は未実施。`realizations/c.py`のC Target互換再エクスポートも工程5まで維持する。本工程ではModel構造とFrontend受理条件を変更しない。
- **仕様/検証**：現行仕様CMPとCVT、READMEの現行API例、STATUS、CHANGELOGを正本ソースから整合させる。名称だけで意味保存を推定せず、正常・拒否テストを維持する。

**次の工程**：工程4c（Python側Interface Mappingに相当するPort名称の整理）。

## 12. 第36回：工程4c（Interface Mapping名称）の結果

- **実施済み（工程4c）**：Python Source Adapter の外部API対応付けを `pyinto.interface_mapping` に配置し、`PortRegistry`→`InterfaceMappingRegistry`、`PortDefinition`→`InterfaceFunctionMapping`、`PortClassDefinition`→`InterfaceClassMapping`、`PortMethodDefinition`→`InterfaceMethodMapping`、`PortNormalizer`→`InterfaceMappingNormalizer` に改名。
- **公開入口**：`convert(interface_mappings=...)` と `PythonFrontend(interface_mappings=...)` を用いる。登録済み関数・クラス・メソッド・属性の対応規則と `admission_declarations` の検証は変更せず、旧 `ports=` キーワード・旧モジュールへの互換エイリアスは設けない。
- **分離して保留する識別子**：`PortType`、`Symbol.port_type`、`ValueKind.PORT_OBJECT`、`port:`キーはModelの外部オブジェクト型・Realizationの型名選択に使われるため、名称だけでなくシリアライズ上の同一性や利用者側の型登録を確認した後に扱う。サンプルAdapterのfactoryは `interface_mapping_registry()` に揃え、登録対象となる外部ライブラリ `demo_ports` 等の実在するモジュール名は変更しない。この保留分は0.2.0で `MappedType`、`Symbol.mapped_type`、`ValueKind.MAPPED_OBJECT`、`mapped:` キーへ改名し、デモの外部ライブラリも `demo_device` とした。
- **責務**：Interface MappingはPythonの既知の外部APIをConstructに対応付ける設定であり、Interfaceそのものを定義する登録機構ではない。Language Constructおよび意味契約・既存の受理条件に変更はない。
- **検証**：Python外部関数、インスタンス、属性、入出力、AdmissionとRealizationの回帰テストを維持し、文書は正本ソースから生成する。工程4cの完了は型情報の名称統一を意味しない。

**次の工程**：工程5（HostとC Target Implementationの論理的な依存境界の整理）。物理的なリポジトリ分割は引き続き行わない。

## 13. 第36回：工程5（Host / C Targetの論理境界）の結果

- **同一リポジトリを維持**し、C Language Implementationのソースを
  `targets/c/src/pyinto_target_c/` へ移動した。`targets/c/pyproject.toml` を設け、
  Python配布名は `pyinto-target-c`、import先は `pyinto_target_c` とする。
  Hostの `src/pyinto/` のパッケージからC Targetを外し、HostのWheelにC実装を含めない。
- HostからC Targetへ逆向きに依存していた `pyinto.realizations.c` の
  再エクスポートを削除した。明示的な利用は
  `from pyinto_target_c import c_bindings` とする。
  `pyinto.convert(..., realizations=c_bindings())` と
  `pyinto.realize(..., realizations=c_bindings())` の意味は変えない。
- C側は、既存の `pyinto.constructs`、`pyinto.realizations.registry`、
  `pyinto.realizations.layout`、`pyinto.realizations.regulation` のみを
  Host側の依存窓口とする。公開済みのこれらのAPIを新しい抽象化に置換しない。
- in-repositoryテストは `targets/c/src` を明示的に参照する。Hostからの
  C実装へのimport禁止と、Cから利用するHostモジュールの限定を静的検査する。
  既存の意味契約・Realization規則・Frontend受理/拒否条件・Factory名 `c_bindings()` と
  内部実装クラス `CTargetPack` は変更しない。
- **未実施事項**：C Targetの別Gitリポジトリ化、公開済みリリースの互換管理、
  開発用Python Realizerの移動（工程6）、公開文書全体の最終校正（工程7）。
  工程5の成果は「論理/パッケージ境界」であり、Target Implementationの
  意味保存を新たに証明したものではない。

**次の工程**：工程6（開発用Python Realizerの非公開テスト資産への整理）。

## 14. 第36回：工程6（開発用Python Realizer）の結果

- **実施済み（工程6）**：旧 `src/pyinto/targets/python/pack.py` を
  `tests/support/python_realizer/pack.py` へ移し、`tests.support.python_realizer.pack`
  として**テストからのみ**利用する。公開 `pyinto.targets.python` モジュールは廃止。
  `python_bindings()` と `PythonTargetPack` は開発用fixture内でのみ維持し、
  Hostの公開APIとはしない。
- **実装境界**：Hostの配布物にはPython Realizerを含めない。
  `pyinto.convert()` / `pyinto.realize()` が非公開Realizerを自動登録・選択することはない。
  HostとC Targetの前工程の依存方向は変更しない。
- **意味契約**：既存テストのPythonコード出力・実行、未登録Realizationと未宣言supportsの
  拒否を維持する。従来の `Initialize` の出力は `n = 2` であり、
  元の型注釈 `n: int = 2` の保持やPython→Model→Python→Modelの完全な往復は
  **この工程では実装しない**。
- **文書**：現在の開発用Realizerに言及するREADME・STATUS・CMP_019、
  CHANGELOG、本計画の正本ソースを更新し日本語Markdownを再生成する。
  第35回時点の監査・仕様と過去の履歴を、事後の事実として書き換えない。
- **範囲外**：公開Python Target Implementationの復活、C Targetの別Gitリポジトリ化、
  PackのRealization拡充、Model・Frontendの受理規則変更。

**次の工程**：工程7（公開文書全体を現行の実装と照合し最終校正する）。

## 15. 第36回：工程7（公開文書の最終整理）の結果

- **実施済み（工程7）**：`devdocs/canonical_sources/vocabulary/canonical.py` の用語定義を
  新しい公開分類へ更新。ModelはInterfaceが所有するConstructと意味契約の
  Target非依存の抽象面とし、Host、Surface、Foundation、Language Construct、
  Python Source Adapter、Interface Mapping、Target Implementation、
  Language Implementation、Interface Implementation、Bundleを区別する。
- **README/STATUS**：現行の2配布物（`pyinto` / `pyinto-target-c`）と
  非公開の開発用Python Realizerを明記。Target Implementationを分類名とし、
  `c_bindings()`や`pack_target`などの残存実装名と区別する。
  古い「工程6で実施予定」の説明を現況に合わせる。
- **現行仕様**：FRT_006のPython側Mappingの説明、CSTのPortオブジェクト形状の
  表題、CVT_003の自動探索の呼称だけを、意味を変えずに修正。
  CST/FRT/CMP/CVTの識別子や既存の受理・拒否の内容は維持。
- **歴史的資料**：この計画書の§1〜§14は作成時点や各工程のスナップショット。
  第14〜35回の監査、STATUSの過去の工程記録、CHANGELOGの旧記述は
  時系列の事実として残す。旧API表記の全件削除は行わない。
- **未実施**：別Gitリポジトリ化、CLI・Bundle・Interface名前空間の新設、
  C/Python Realizationの実現範囲拡張。これらを工程7の達成内容とみなさない。

**次の工程**：工程8（Host/C Targetの配布・参照境界を最終監査し、
文書と配布物の一致を検証する）。

## 16. 第36回：工程8（総合検証・公開境界監査）の結果

**工程8の総合監査を完了した。対象は工程7の成果物を基準とする。**
この節は監査実施後の状態を記録するものであり、§1〜§15の過去時点の記述は
その時点の設計・移行履歴として維持する。

| 監査対象 | 確認した事実 |
|---|---|
| 配布境界 | Host `pyinto` とC Language Implementation `pyinto-target-c` は別Wheel。Hostのみの環境にC実装は存在せず、後者を追加すると利用可能 |
| 依存方向 | Host→C Targetのimportを禁止する既存のAST検査を維持。C側は公開されたConstruct / Realization APIからのみ参照 |
| 公開入口 | `convert()` / `realize()` は `realizations=` の明示指定を要求。`c_bindings()`から選択したRealizationRegistryを利用 |
| 開発用資産 | Python Realizerは`tests/support/python_realizer/`に保持。Contraceの開発用契約モジュール`pyinto.contracts`もソースに残すが、Host Wheelからは除外 |
| 独立インストール | Host単体、およびHost+C Targetをそれぞれ新規仮想環境へオフラインで導入し、両環境の`pip check`に成功 |
| 出力と拒否 | Wheel由来のAPIで`print("hello")`をCへ変換し、生成Cを`gcc -std=c11 -Wall -Wextra -Werror -pedantic`でビルド・実行。未実装`Arithmetic`の明示拒否も確認 |
| 配布メタデータ | `pyinto-target-c` は `pyinto==0.0.1` に依存。バージョン変更時は両者の整合性が必要 |
| 品質検証 | pytest+Contrace **1,394件成功**、Ruff check/format、basedpyright（0 errors/0 warnings）、文書生成・整合性、2 Wheelビルドを確認 |

**修正した事項**：Host Wheelに不要な`pyinto.contracts`の開発用モジュールが
以前は含まれていたため、`pyproject.toml` のパッケージ探索から
`pyinto.contracts` とその子パッケージを除外した。ビルドの中間ファイルを
一度削除した**クリーンビルド**でWheelの内容を再確認した。
開発環境のソースツリー上ではContrace検証を引き続き使用できる。
配布境界・明示選択・メタデータについて3件の回帰テストを追加。

**工程8の完了範囲**：新名称と2配布物の論理境界、現在の公開API、
独立したインストール経路、正常系と拒否系、文書と実装の対応を確認。
**別Gitリポジトリへの分割は行っていない。**
また、既存C Language Implementationの未実装Construct、開発用Python Realizerの
型注釈非保持、同名Symbolに関する意味保存検証課題は継続する。
これはすべてのTarget実装の意味保存を証明したという結果ではない。

**次工程への申し送り**：将来の別リポジトリ化では、同一リポジトリ内の
`targets/c/` を既存の公開APIとWheel構成を維持して移管する。
追加機能・Interface名前空間・CLI・Bundleの新設は本工程の対象外。

## 17. 第50回：C Realizerのテスト資産化とHost単体配布

**第50回の方針転換**：当初の別配布物化の方針を更新し、C Targetを
`targets/c/src/pyinto_target_c/` から `tests/support/c_realizer/` に移動した。
Python参照Realizerと同様、C参照Realizerは開発・回帰試験の資産として残すが、
配布物としての `pyinto-target-c` は今回のソース構成には存在しない。
本文の§1〜§16にある別Wheelの記述は、各工程の**歴史的記録**であり、
現行の利用方法を示さない。現行の導入方法はREADME/STATUSを正とする。

- **配布**：`pyinto` だけをWheelにまとめ、C/Python RealizerとContrace契約は含めない。
- **依存境界**：C参照Realizerのimportは公開Construct・Interface・
  Model・Realization APIに制限し、Hostから参照Realizerへの逆方向依存を禁止する。
- **試験資産**：Cの実装・Admission拒否・Template/Slot生成テストを残す。
  Python参照Realizerも引き続き非公開。
- **サンプル**：Cコード生成はリポジトリ内の開発用参照実装で実行可能だが、
  利用者向けのインストール可能なCパッケージの提供は本工程の目的ではない。
- **将来**：C Targetの正式な製品化・再配布は必要になった時点で別途判断する。
