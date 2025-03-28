import lab as B
import numpy as np

from neuralprocesses import _dispatch
from neuralprocesses.numdata import num_data
from neuralprocesses.model import Model
from neuralprocesses.model.util import fix_noise as fix_noise_in_pred

__all__ = ["loglik"]


@_dispatch
def loglik(
    state: B.RandomState,
    model: Model,
    contexts: list,
    xt,
    yt,
    *,
    num_samples=1,
    batch_size=16,
    normalise=False,
    fix_noise=None,
    dtype_lik=None,
    **kw_args,
):
    """Log-likelihood objective.

    Args:
        state (random state, optional): Random state.
        model (:class:`.Model`): Model.
        xc (input): Inputs of the context set.
        yc (tensor): Output of the context set.
        xt (input): Inputs of the target set.
        yt (tensor): Outputs of the target set.
        num_samples (int, optional): Number of samples. Defaults to 1.
        batch_size (int, optional): Batch size to use for sampling. Defaults to 16.
        normalise (bool, optional): Normalise the objective by the number of targets.
            Defaults to `False`.
        fix_noise (float, optional): Fix the likelihood variance to this value.
        dtype_lik (dtype, optional): Data type to use for the likelihood computation.
            Defaults to the 64-bit variant of the data type of `yt`.

    Returns:
        random state, optional: Random state.
        tensor: Log-likelihoods.
    """
    float = B.dtype_float(yt)
    float64 = B.promote_dtypes(float, np.float64)

    # For the likelihood computation, default to using a 64-bit version of the data
    # type of `yt`.
    if not dtype_lik:
        dtype_lik = float64

    # Sample in batches to alleviate memory requirements.
    logpdfs = None
    done_num_samples = 0
    while done_num_samples < num_samples:
        # Limit the number of samples at the batch size.
        this_num_samples = min(num_samples - done_num_samples, batch_size)

        # print("yt stats:", B.min(yt), B.max(yt))
        # print("context yc stats:", B.min(contexts[0][1]), B.max(contexts[0][1]))

        # Perform batch.
        state, pred = model(
            state,
            contexts,
            xt,
            num_samples=this_num_samples,
            dtype_enc_sample=float,
            dtype_lik=dtype_lik,
            **kw_args,
        )
        # print("Predicted mean (transformed) stats:", B.min(pred.mean), B.max(pred.mean))
        # print("Pred
        # icted var stats:", B.min(pred.var), B.max(pred.var))
        # logpdf = pred.logpdf(yt)
        # print("logpdf stats:", B.min(logpdf), B.max(logpdf))

        pred = fix_noise_in_pred(pred, fix_noise)
        this_logpdfs = pred.logpdf(B.cast(dtype_lik, yt))

        # If the number of samples is equal to one but `num_samples > 1`, then the
        # encoding was a `Dirac`, so we can stop batching. Also, set `num_samples = 1`
        # because we only have one sample now. We also don't need to do the
        # `logsumexp` anymore.
        if num_samples > 1 and B.shape(this_logpdfs, 0) == 1:
            logpdfs = this_logpdfs
            num_samples = 1
            break

        # Record current samples.
        if logpdfs is None:
            logpdfs = this_logpdfs
        else:
            # Concatenate at the sample dimension.
            logpdfs = B.concat(logpdfs, this_logpdfs, axis=0)

        # Increase the counter.
        done_num_samples += this_num_samples

    # Average over samples. Sample dimension should always be the first.
    logpdfs = B.logsumexp(logpdfs, axis=0) - B.cast(dtype_lik, B.log(num_samples))

    if normalise:
        # Normalise by the number of targets.
        logpdfs = logpdfs / B.cast(dtype_lik, num_data(xt, yt))

    return state, logpdfs


@_dispatch
def loglik(state: B.RandomState, model: Model, xc, yc, xt, yt, **kw_args):
    return loglik(state, model, [(xc, yc)], xt, yt, **kw_args)


@_dispatch
def loglik(model: Model, *args, **kw_args):
    state = B.global_random_state(B.dtype(args[-2]))
    state, logpdfs = loglik(state, model, *args, **kw_args)
    B.set_global_random_state(state)
    return logpdfs





