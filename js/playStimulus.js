let audioCtx = null;
let audioBuffer = null;
const otherEar = ear => ear === "left" ? "right" : "left";

async function loadStimulus() {
    if (audioBuffer) return;
    audioCtx ??= new AudioContext();
    const response = await fetch('/stimulus');
    const arrayBuffer = await response.arrayBuffer();
    audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
}

function playInEar(ear, startTime) {
    const source = audioCtx.createBufferSource();
    const panner = audioCtx.createStereoPanner();
    source.buffer = audioBuffer;
    panner.pan.value = ear === "left" ? -1 : 1;
    source.connect(panner).connect(audioCtx.destination);
    source.start(startTime);
}

function playBeep(startTime, duration, freq=440, volume=0.5) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = freq;
    gain.gain.value = volume;
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(startTime);
    osc.stop(startTime + duration);
}

async function playTOJ(firstEar, gapMs, beepDuration=0.5) {
    await loadStimulus();
    const now = audioCtx.currentTime;
    playBeep(now, beepDuration);
    playInEar(firstEar, now + beepDuration + 1);
    playInEar(otherEar(firstEar), now + beepDuration + 1 + audioBuffer.duration + (gapMs / 1000));
}