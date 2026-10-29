class MicrophoneProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const channel = inputs[0]?.[0];
        if (channel) {
            const output = new Int16Array(channel.length);
            for (let i = 0; i < channel.length; i++) {
                const value = Math.max(-1, Math.min(1, channel[i]));
                output[i] = value < 0 ? value * 32768 : value * 32767;
            }
            this.port.postMessage(output.buffer, [output.buffer]);
        }
        return true;
    }
}
registerProcessor("microphone-processor", MicrophoneProcessor);
