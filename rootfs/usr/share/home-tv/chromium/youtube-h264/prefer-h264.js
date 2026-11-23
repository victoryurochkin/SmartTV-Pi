(() => {
    const softwareCodec = /\b(?:vp0?[89]|x-vnd\.on2\.vp[89]|av01|av1)\b/i;
    const canPlayType = HTMLMediaElement.prototype.canPlayType;
    HTMLMediaElement.prototype.canPlayType = function (type) {
        return softwareCodec.test(type) ? '' : canPlayType.call(this, type);
    };

    if (window.MediaSource) {
        const isTypeSupported = MediaSource.isTypeSupported;
        MediaSource.isTypeSupported = function (type) {
            return !softwareCodec.test(type) && isTypeSupported.call(this, type);
        };
    }

    if (navigator.mediaCapabilities) {
        const decodingInfo = navigator.mediaCapabilities.decodingInfo;
        navigator.mediaCapabilities.decodingInfo = function (configuration) {
            if (softwareCodec.test(configuration?.video?.contentType)) {
                return Promise.resolve({ supported: false, smooth: false, powerEfficient: false });
            }
            return decodingInfo.call(this, configuration);
        };
    }
})();
