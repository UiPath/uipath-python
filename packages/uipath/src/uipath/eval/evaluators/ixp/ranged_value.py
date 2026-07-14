from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import variance
from typing import Final, Generic, TypeVar

from ._compat import round_to_significant_figures

# NOTE: !! IMPORTANT !!
#
# Modifying the logic to convert raw metrics into summary metrics will require
# you to update the cache version in `metadata_store` in
# `_user_model_summary_metrics_cache_key` since summary metrics get cached.
#
# To ensure these errors get caught more easily also please DO NOT ADD ANY
# DEFAULT FIELDS to any of the types in this file.
#
# NOTE: !! IMPORTANT !!


__all__ = ("RangedValue",)


TypeT = TypeVar("TypeT", bound=float | int)


@dataclass(slots=True, frozen=True)
class RangedValue(Generic[TypeT]):
    value: TypeT
    variability: float | None

    @staticmethod
    def from_mean(
        numerators: Sequence[int],
        denominators: Sequence[float],
        zero_division_result: float,
    ) -> RangedValue[float]:
        """
        `numerators`: Sequence of numerators for each document
        `denominators`: Sequence of denominators for each document
        `zero_division_result`: Value to use when sum of denominators is zero

        `numerators` and `denominators` must have the same length, which is N,
        the number of documents

        # Calculation if no zero denominators

        The mean value is given by

        mean_value = sum_i(numerators[i]) / sum_i(denominators[i])

        which can also be viewed as a weighted mean of the individual
        document values, with the denominators as weights,

        mean_value = (sum_i denominators[i] * value[i]) / sum_i denominators[i],

        where weights[i] = denominators[i]
        and value[i] = numerators[i] / denominators[i] is the value for
        document i.

        There are multiple techniques for estimating the variance of a weighted
        mean, depending on the context of the underlying data. In our context,
        of a weighted mean where the weights relate to the denominator per
        document, but there is also considerable uncertainty about the
        differences in behavior between documents. We can say that documents
        with larger denominators are both more important and contribute more to
        the overall mean, but we also have considerable uncertainty about the
        differences in behavior between documents: so just one heavily-weighted
        document and all other documents being lightly-weighted is not a good
        sample.

        We therefore use the approach set out at
        https://en.wikipedia.org/w/index.php?title=Weighted_arithmetic_mean&oldid=1311125396&section=19#Reliability_weights
        to estimate the variance of the weighted mean. This approach is based
        on the idea of "reliability weights", where the weights (our
        denominators) are viewed as indicating the reliability of each
        document's value. Setting

        values[i] = numerators[i] / denominators[i],

        this approach gives the variance as

        variance = ( sum_i denominators[i] * (values[i] - mean_value)**2 )
                    / ( 1 - sum_i (denominators[i]**2) / (sum_i denominators[i])**2 ).

        # Supplement to the calculation if there are some zero denominators

        The above calculation assumes that there are no zero denominators. If
        we have some documents with zero denominators, we model them as having
        numerators sampled from a second distribution. We estimate the variance
        of that distribution as the sample variance of the numerators for
        documents with zero denominators. The variance for these
        zero-denominator documents in the mean is then this variance, divided
        by (sum_i denominators[i])**2, the square of the overall denominator in
        the weighted mean.

        # Variability

        We then add the final variances for documents with non-zero and zero
        denominators together to get the total variance. We choose the
        associated variability to a kind of standard error of the weighted
        mean:

        variability = sqrt( variance / effective_sample_size ).

        Given the combined role of number of documents and the weight of each
        document in determining effective size of our sample, we, somewhat
        ad-hoc, define the effective sample size as

        effective_sample_size = sqrt( N * sum_i denominators[i] ),

        where N is the number of documents.
        """
        assert len(numerators) == len(denominators), (
            f"Length of numerators, {len(numerators)}, and length of "
            f"denominators, {len(denominators)}, must be equal."
        )
        sum_denominators = sum(denominators)
        mean_value = (
            sum(numerators) / sum_denominators
            if sum_denominators > 0
            else zero_division_result
        )
        if sum_denominators == 0 or len(denominators) == 1:
            return RangedValue(value=mean_value, variability=None)

        total_variance_of_the_mean = _get_total_variance_of_mean(
            numerators=numerators, denominators=denominators
        )

        if total_variance_of_the_mean is None:
            return RangedValue(value=mean_value, variability=None)

        variability = math.sqrt(
            total_variance_of_the_mean
            / math.sqrt(len(numerators) * sum_denominators)
        )
        return RangedValue(
            value=mean_value,
            variability=round_to_significant_figures(
                target=variability,
                num_figures=_NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY,
            ),
        )

    @staticmethod
    def from_sum(
        counts: Sequence[int], reference_counts: Sequence[int]
    ) -> RangedValue[int]:
        """
        `counts`: Sequence of counts for each document
        `reference_counts`: Sequence of reference_counts for each document,
            which will inform the model for the variability calculation

        `counts` and `reference_counts` must have the same length.

        # Explanation of model for variability

        This model is the same as that used for `RangedValue.from_mean`, except
        that we are calculating the sum of the counts, rather than a mean.
        Accordingly, we use exactly the same calculation with the counts
        corresponding to the numerators, and the reference_counts corresponding
        to the denominators. We scale the final variability up by
        sum_i reference_counts[i] to reflect that we are calculating the sum,
        rather than the mean.
        """
        assert len(counts) == len(reference_counts), (
            f"Length of counts, {len(counts)}, and length of "
            f"reference_counts, {len(reference_counts)}, must be equal."
        )
        sum_value = sum(counts)
        if sum(reference_counts) == 0 or len(reference_counts) == 1:
            return RangedValue(value=sum_value, variability=None)

        total_variance_of_the_mean = _get_total_variance_of_mean(
            numerators=counts, denominators=reference_counts
        )

        if total_variance_of_the_mean is None:
            return RangedValue(value=sum_value, variability=None)

        variability = (sum(reference_counts) ** 0.75) * math.sqrt(
            total_variance_of_the_mean / math.sqrt(len(counts))
        )
        return RangedValue(
            value=sum_value,
            variability=round_to_significant_figures(
                target=variability,
                num_figures=_NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY,
            ),
        )


_MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY: Final[int] = 10
_NUM_SIGNIFICANT_FIGURES_FOR_VARIABILITY: Final[int] = 1


def _get_total_variance_of_mean(
    numerators: Sequence[int], denominators: Sequence[float]
) -> float | None:
    """See docstring of `RangedValue.from_mean` for explanation of this
    variance calculation. We exclude cases where there are too few documents
    with non-zero denominators to get a reliable estimate of the variance.

    Assumes that `numerators` and `denominators` have the same length, and that
    the denominators sum to a non-zero value.
    """
    if len(denominators) < (
        _MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY
    ):
        return None

    # For each individual document, get the number needed to feed into our
    # model for the variance calculation
    numerators_with_non_zero_denominator: list[int] = []
    non_zero_denominators: list[float] = []
    numerators_with_zero_denominator: list[int] = []
    for numerator, denominator in zip(numerators, denominators, strict=True):
        if denominator != 0.0:
            numerators_with_non_zero_denominator.append(numerator)
            non_zero_denominators.append(denominator)
            continue
        numerators_with_zero_denominator.append(numerator)

    if len(non_zero_denominators) < (
        _MINIMUM_NUM_NON_ZERO_DENOMINATORS_FOR_VARIABILITY
    ):
        return None

    # Calculate variance for non-zero denominators
    sum_denominators = sum(non_zero_denominators)
    mean_value_for_non_zero = (
        sum(numerators_with_non_zero_denominator) / sum_denominators
    )
    sum_squared_denominators = sum(
        denominator**2 for denominator in non_zero_denominators
    )
    variance_for_non_zero_denominators = sum(
        denominator * (numerator / denominator - mean_value_for_non_zero) ** 2
        for numerator, denominator in zip(
            numerators_with_non_zero_denominator,
            non_zero_denominators,
            strict=True,
        )
    ) / (sum_denominators - sum_squared_denominators / sum_denominators)

    variance_for_zero_denominators = (
        variance(numerators_with_zero_denominator)
        if len(numerators_with_zero_denominator) > 1
        else 0.0
    ) / sum_denominators**2

    return variance_for_non_zero_denominators + variance_for_zero_denominators
