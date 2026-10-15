<!--
この文書は `shikumi-devdoc` により生成された日本語の canonical document です。
Canonical source: `devdocs/canonical_sources/specification/conversion.py`
内容を変更する場合は正本を編集し、再生成してください。
英語の published document は正本からの派生として README.md 等と docs/ に配置します。
翻訳の進捗は docs/TRANSLATION_STATUS.md を参照してください。
-->

# Conversion API

初期の公開 Python API。CLI / Cartridge 自動発見は未実装。

## CVT_001

`pyinto.convert(source, *, realizations, interface_mappings=None, admission=None)` は Python ソース文字列を受け、`PythonFrontend` で正規化した後、指定された `RealizationRegistry` とTarget専用Artifact Sessionで実現し、Sessionが提出した成果物オブジェクトをそのまま返す。Target の推測・暗黙の C 選択は行わない。Construct 提供者の `AdmissionRegistry` は明示された `admission` を優先し、未指定なら明示された `InterfaceMappingRegistry` の契約登録を利用する。

title: ソースからの共通変換入口

level: MUST

related: [CST_006](construct.md#cst_006)

## CVT_002

`pyinto.realize(program, *, realizations, admission=None)` は既存の Construct Tree を変更せず、渡された `RealizationRegistry` で選択・実現し、Targetが提出した任意型の成果物を返す。同じ Program を異なる Registry で繰り返し実現できる。`admission` を指定しない場合は Language Construct の契約登録だけを用いる。外部Constructは提供者登録を明示的に渡さない限り拒否する。

title: 既存 Model の任意 Realization

level: MUST

related: [CST_001](construct.md#cst_001)

## CVT_003

`realizations` に `RealizationRegistry` 以外を渡した場合、または `realize` に Construct 以外を渡した場合は TypeError とし、未知の Construct・未対応 Target 操作は既存の `ConstructError` として明示的に失敗する。登録された外部Interface Mappingが必要な場合、呼び出し側が `interface_mappings=` を明示して渡す。`admission` に不正な型を渡した場合も TypeError とする。未登録 Construct は Target のレシピがあっても拒否し、既存Language Construct契約の上書きを許さない。現在はRealizerやInterfaceの自動探索・解決を行わない。

title: 依存の明示と失敗

level: MUST

## CVT_004

`realize`と`convert`の成果物返却型は`object`であり、Hostは文字列化・ファイル保存・最終テキスト結合を行わない。Realizerが変換要求ごとに生成するSessionの`finish()`結果を返す。Compositionでは既存Layoutを`accept_composition(layout, context)`でSessionへ渡し、最終描画はTargetが選んだ実装で行う。Structuralでは全Constructの`visit(node, ctx)`を処理した後に提出を要求する。失敗時は`finish()`を呼ばず、次の変換で状態を再利用しない。

title: Target所有の成果物と提出ライフサイクル

level: MUST

## CVT_005

`convert()` は入力ASTのトップレベル同期・無引数・非装飾 `def __pyinto_runtime__():` を検出し、通常のFrontend Modelから除外する。Target Packは `purpose` でSourceをどう扱うかを宣言する。`conversion`（既定）は変換目的であり、関数があれば拒否する。`inspection` はSourceを読む目的であり、関数があっても受理するが実行せず `finish()` を呼ぶ。`inspection` は `semantics = "projection"` を必須とする。`execution` は実行目的であり、`runtime` に `required`（関数がなければ拒否）または `optional`（あれば呼び出し・なければ `RUNTIME_ABSENT` を渡す）を必ず宣言する。`runtime` と `runtime_schema` は `execution` でだけ宣言でき、それ以外の目的や未知の値は登録時に拒否する。`realize()` は元ソースを持たないため `required` では拒否し、`optional` には `RUNTIME_ABSENT` を渡す。目的の宣言はComposition / Structuralと独立である。

title: Targetの目的とRuntime関数の利用契約

level: MUST

## CVT_006

`execution` のTargetでは、Hostは静的Modelの検証とDispatchの後に、**利用者が信頼するPythonソース**を通常のPythonとして一度だけ実行し、`__pyinto_runtime__()` を一度呼んで得た戻り値Rを `Session.finish(R)` に渡す。`optional` で関数がない場合も `Session.finish(RUNTIME_ABSENT)` を呼び、`None` と不在を区別する。Runtime関数内部の構文はFrontendで検証しない。Rの意味はTargetが所有し、`runtime_schema` があればHostがRの型・値の契約を `finish(R)` の直前に検証する。宣言がなければRのスキーマ検証は行わない。実行失敗は静的処理へ自動フォールバックせず例外を伝播する。Source文字列には実ファイルやパッケージコンテキストがないため、新規の一時モジュール名前空間で実行し、終了後にその一時モジュール登録を解除する。実行に伴うトップレベル副作用は起こり得る。pyintoはサンドボックスではなく、信頼できないソースを入力してはならない。

title: Runtime実行の信頼境界とSessionへの受け渡し

level: MUST

## CVT_007

Target PackはRuntime値Rの追加契約として `runtime_schema` に通常の型オブジェクトまたは `Callable[[object], bool]` を宣言できる。対象は `purpose = "execution"` のTargetに限定し、省略時は追加検査しない。HostはRの実行取得後、Sessionの `finish(R)` の直前に検査する。通常の型オブジェクトは `isinstance(R, schema)` だけで判定し、ジェネリック式 `list[int]` 等は直接指定せず検証関数を使う。検証関数の引数はRのみ、戻り値は厳密なboolとし、真のときだけ受理する。スキーマ不一致、不正な戻り値、検証関数の例外では `RuntimeSchemaError` を送出し `finish` へ進まない。例外原因は保持する。検証はRを変換せず、同じオブジェクトを渡す。`optional` の不在センチネル `RUNTIME_ABSENT` は検証対象外だが、関数から返った `None` は検証する。Schemaの内容はTargetが所有し、Hostは独自の型システムを持たない。

title: Targetが宣言するRuntimeスキーマの検証

level: MUST
