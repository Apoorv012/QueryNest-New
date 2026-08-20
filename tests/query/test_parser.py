from datetime import date

from core.query.parser import parse_query


class TestRelativeDates:
    def test_last_6_months(self):
        result = parse_query("AI papers last 6 months")
        today = date.today()  # noqa: DTZ011
        assert result.date_from is not None
        assert result.date_to == today
        assert (result.date_to - result.date_from).days >= 170
        assert (result.date_to - result.date_from).days <= 200
        assert result.query == "AI papers"

    def test_last_year(self):
        result = parse_query("deadlock prevention last year")
        today = date.today()  # noqa: DTZ011
        assert result.date_from is not None
        assert result.date_to == today
        assert (result.date_to - result.date_from).days >= 350

    def test_past_3_years(self):
        result = parse_query("transformer architecture past 3 years")
        today = date.today()  # noqa: DTZ011
        assert result.date_from is not None
        assert (today - result.date_from).days >= 1080


class TestExactYear:
    def test_in_2024(self):
        result = parse_query("papers in 2024")
        assert result.date_from == date(2024, 1, 1)
        assert result.date_to == date(2024, 12, 31)
        assert result.query == "papers"

    def test_in_2022(self):
        result = parse_query("find results in 2022")
        assert result.date_from == date(2022, 1, 1)
        assert result.date_to == date(2022, 12, 31)


class TestDateRange:
    def test_from_to_inclusive(self):
        result = parse_query("from 2020 to 2023")
        assert result.date_from == date(2020, 1, 1)
        assert result.date_to == date(2023, 12, 31)

    def test_dash_range(self):
        result = parse_query("2020-2023")
        assert result.date_from == date(2020, 1, 1)
        assert result.date_to == date(2023, 12, 31)

    def test_em_dash_range(self):
        result = parse_query("2020–2023")
        assert result.date_from == date(2020, 1, 1)
        assert result.date_to == date(2023, 12, 31)


class TestBeforeAfter:
    def test_before_year(self):
        result = parse_query("papers before 2022")
        assert result.date_from is None
        assert result.date_to == date(2021, 12, 31)
        assert result.query == "papers"

    def test_after_year(self):
        result = parse_query("papers after 2023")
        assert result.date_from == date(2024, 1, 1)
        assert result.date_to is None
        assert result.query == "papers"

    def test_before_after_year_symmetry_excludes_the_named_year(self):
        # `before YYYY` and `after YYYY` should both exclude YYYY itself:
        # before/after are exclusive bounds, not inclusive ones.
        before = parse_query("papers before 2020")
        after = parse_query("papers after 2020")
        assert before.date_to == date(2019, 12, 31)
        assert after.date_from == date(2021, 1, 1)
        # Neither bound includes any day within 2020.
        assert before.date_to < date(2020, 1, 1)
        assert after.date_from > date(2020, 12, 31)


class TestNoDate:
    def test_no_date_expression(self):
        result = parse_query("what is a transformer")
        assert result.date_from is None
        assert result.date_to is None
        assert result.query == "what is a transformer"


class TestQueryCleaning:
    def test_date_removed_from_query(self):
        result = parse_query("transformer architecture in 2024")
        assert "2024" not in result.query
        assert "transformer" in result.query

    def test_range_removed(self):
        result = parse_query("papers from 2020 to 2023 about AI")
        assert "2020" not in result.query
        assert "2023" not in result.query
        assert "papers" in result.query
        assert "AI" in result.query
