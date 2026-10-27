def 結果を候補へ(
    課題ID: str,
    課題: dict[str, list[dict[str, Any]]],
    結果: object,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Preserve legacy attempt2 and HDS HOLD provenance; materialize only eligible portfolio attempt1."""
    行群 = 結果.get("results") if isinstance(結果, dict) else None
    障害 = 結果.get("error") if isinstance(結果, dict) else "invalid_worker_result"
    if not isinstance(行群, list) or len(行群) != len(課題["test"]):
        行群 = []
        障害 = 障害 or "result_count_mismatch"
    出力, 保留記録 = [], []
    for 位置, 対 in enumerate(課題["test"]):
        行 = 行群[位置] if 位置 < len(行群) and isinstance(行群[位置], dict) else {}
        予測 = 行.get("answer")
        保留行 = None
        if 格子か(予測):
            候補 = deepcopy(予測)
        else:
            候補 = deepcopy(対["input"])
            理由 = "solver_hold" if 予測 is None else "invalid_prediction"
            if 障害:
                理由 = str(障害)
            保留行 = {
                "task_id": 課題ID,
                "test_index": 位置,
                "reason": 理由,
                "solver_status": 行.get("status"),
                "solver_hold_reasons": _保留理由ラベル群(行.get("reasons")),
            }
            保留記録.append(保留行)

        # Freeze the exact legacy normalization BEFORE attempt1 can change.
        第二候補 = 行.get("second_answer")
        if not 格子か(第二候補) or 第二候補 == 候補:
            第二候補 = 候補
        v61第二候補 = deepcopy(第二候補)
        portfolio = deepcopy(行.get("portfolio_diagnostics")) if isinstance(行.get("portfolio_diagnostics"), dict) else None
        portfolio候補 = 行.get("portfolio_attempt1")
        scope = (
            保留行 is not None
            and 保留行["reason"] == "solver_hold"
            and 行.get("hds_primary_hold") is True
            and 候補 == 対["input"]
            and v61第二候補 != 対["input"]
        )
        qualification_ok = _portfolio_qualification_is_valid(
            portfolio.get("selected_qualification") if portfolio is not None else None,
            len(課題["train"]),
        )
        materialized = (
            scope and qualification_ok and 格子か(portfolio候補)
            and portfolio候補 != 対["input"] and portfolio候補 != v61第二候補
        )
        if materialized:
            候補 = deepcopy(portfolio候補)
        assert 第二候補 == v61第二候補, "portfolio changed v61 attempt2"
        if 保留行 is not None:
            保留行["hds_primary_hold"] = 保留行["reason"] == "solver_hold"
            保留行["attempt1_source"] = "external_portfolio" if materialized else "input_copy_fallback"
            保留行["true_input_copy_fallback"] = 候補 == 対["input"]
            保留行["v61_attempt2_preserved"] = 第二候補 == v61第二候補
            if portfolio is not None:
                portfolio["materialized"] = bool(materialized)
                portfolio["formatter_scope_passed"] = bool(scope)
                portfolio["formatter_full_train_qualification_passed"] = bool(qualification_ok)
                保留行["portfolio"] = portfolio
        出力.append({"attempt_1": deepcopy(候補), "attempt_2": deepcopy(第二候補)})
    return 出力, 保留記録
