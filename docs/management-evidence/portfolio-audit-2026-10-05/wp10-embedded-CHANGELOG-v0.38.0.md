# v0.38.0

- 未取得のSP等が降順の先頭に出る不具合を修正。None/空文字は昇順・降順とも末尾。0は有効値。全件sortとstreaming top-Nの契約を統一。
- 0頭の成功snapshotでGUI状態が更新されない問題を修正。旧Reading表示を消し、現在の件数・取得元情報を表示。
- ULV設定生成でPE配置とEXE hashを別のopenで読む競合を修正。同一の通常ファイルhandleで両方を読み、取得前後のidentity・size・mtime/ctime等を照合。途中の内容変更・差替えは生成中止。
- 新規8テストをv0.37実装に適用して6 FAIL / 2 PASSを確認。修正後は8 PASS、全407テスト・28gate PASS。
- DX12版1.0.1〜1.0.5、基礎能力値、CSV意味記録、2snapshot、Evidence条件を維持。実ゲーム未検証・confirmed builds 0・NO_GO。
