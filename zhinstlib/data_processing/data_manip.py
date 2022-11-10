import numpy as np


def chunkify_timetrace(signal, reference):
    idxs = np.arange(0, len(signal) - 1)

    diff_ref = np.diff(reference)
    diff_nonzero = diff_ref != 0

    diff_ref, idxs = diff_ref[diff_nonzero], idxs[diff_nonzero]

    signal_chunks = []
    for ii in range(len(idxs) - 1):
        if (diff_ref[ii] == -1) and (diff_ref[ii + 1] == 1):
            signal_chunks.append(signal[idxs[ii] : idxs[ii + 1]])

    if diff_ref[-1] == -1:
        signal_chunks.append(signal[idxs[-1] :])

    return signal_chunks


def chunkify_timetrace(signal, reference):
    """
    :param signal: can be a (N,) array or a (M,N) array
    :param reference: a (N,) TTL-like array containing the reference to chunkify
    :return: list of chunkified signal
    """
    if signal.ndim == 1:
        signal = signal[np.newaxis, :]
    idxs = np.arange(0, signal.shape[1] - 1)

    reference = np.where(reference >= reference.mean(), 1, 0).astype(int)

    diff_ref = np.diff(reference)
    diff_nonzero = diff_ref != 0

    diff_ref, idxs = diff_ref[diff_nonzero], idxs[diff_nonzero]

    signal_chunks = []
    # TODO: clean up this horrible mess of if clauses
    for ii in range(len(idxs) - 1):
        if (diff_ref[ii] == -1) and (diff_ref[ii + 1] == 1):
            signal_chunks.append(signal[:, idxs[ii] : idxs[ii + 1]])

    if diff_ref[-1] == -1:
        signal_chunks.append(signal[:, idxs[-1] :])

    if signal.ndim == 1:
        signal_chunks = signal_chunks[0]

    return signal_chunks


def special_chunkification(signal, reference, spike_SNR=1000, reference_percs=[1, 10]):
    """
    Now the reference has not been thresholded in advance
    """

    diff_ref = np.diff(reference)

    derivative_thresh = (
        np.diff(np.percentile(abs(diff_ref), reference_percs)) * spike_SNR
    )

    prev_der = 0
    chunk_blk = []
    signal_chunks = []
    prev_ders = []

    for ii in range(len(diff_ref)):

        der_value = diff_ref[ii]

        # If the derivative is below theshold, set it to zero
        if abs(der_value) < derivative_thresh:
            # If the previous derivative was positive, and now it is zero, then this is the left edge of the pulse
            if prev_der > 0:
                chunk_blk.append(ii)
            prev_der = 0
        else:
            # If the previous derivative was zero, but now is negative, then this is the right edge of the pulse
            if prev_der == 0 and der_value < 0:
                chunk_blk.append(ii)
            prev_der = der_value
        if len(chunk_blk) == 2:
            # If the chunk length is 2, it means that a pulse has been fully detected
            signal_chunks.append(signal[chunk_blk[0] + 1 : chunk_blk[1] + 1])
            chunk_blk = []

    return signal_chunks
