let audioCtx = null;
let audioBuffer = null;
const spondeeBuffers = new Map();
const otherEar = ear => ear === "left" ? "right" : "left";
const dbToGain = db => Math.pow(10, db / 20);

async function loadBuffer(url) {
    audioCtx ??= new AudioContext();
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    return await audioCtx.decodeAudioData(arrayBuffer);
}

async function loadStimulus() { audioBuffer ??= await loadBuffer('/stimulus.wav'); }

async function loadSpondee(word) {
    if (!spondeeBuffers.has(word)) spondeeBuffers.set(word, await loadBuffer(`/spondees/${word}.wav`));
    return spondeeBuffers.get(word);
}

function playBuffer(buffer, startTime, levelDb, pan=null) {
    const source = audioCtx.createBufferSource();
    const gain = audioCtx.createGain();
    source.buffer = buffer;
    gain.gain.value = dbToGain(levelDb);
    let node = source.connect(gain);
    if (pan !== null) {
            const panner = audioCtx.createStereoPanner();
            panner.pan.value = pan;
            node = node.connect(panner);
        }
    node.connect(audioCtx.destination);
    source.start(startTime);
}

function playInEar(ear, startTime, levelDb) {
    playBuffer(audioBuffer, startTime, levelDb, ear === "left" ? -1 : 1);
}

function playBeep(startTime, duration, levelDb, freq=440) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = freq;
    gain.gain.value = dbToGain(levelDb);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(startTime);
    osc.stop(startTime + duration);
}

async function playSpondee(word, levelDb) {
    const buffer = await loadSpondee(word);
    await audioCtx.resume();
    playBuffer(buffer, audioCtx.currentTime, levelDb);
}

async function playTOJ(firstEar, gapMs, levelDb, beepDuration=0.5) {
    await loadStimulus();
    await audioCtx.resume();
    const now = audioCtx.currentTime;
    playBeep(now, beepDuration, levelDb);
    playInEar(firstEar, now + beepDuration + 1, levelDb);
    playInEar(otherEar(firstEar), now + beepDuration + 1 + audioBuffer.duration + (gapMs / 1000), levelDb);
}
