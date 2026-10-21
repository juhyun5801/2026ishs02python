'use strict';

// 측정 중에는 선택한 모터음을 합성하고, 결과 전환 때 로컬 팡파르를 한 번 재생한다.
(function (root) {
  class GaugeSound {
    constructor(createContext, createAudio) {
      this.createContext = createContext || (() => new root.AudioContext());
      this.voice = null;
      this.failed = false;
      this.phase = null;
      this.fanfare = null;
      try {
        this.fanfare = createAudio ? createAudio() : typeof root.Audio === 'function' ? new root.Audio('sounds/score-fanfare.wav') : null;
        if (this.fanfare) {
          this.fanfare.preload = 'auto';
          if (this.fanfare.load) this.fanfare.load();
        }
      } catch (_) { this.fanfare = null; }
    }

    update({ active, score, phase, enabled = true, volume = 35 }) {
      const finished = this.phase === 'measuring' && phase === 'result';
      this.phase = phase || null;
      const v = Number(volume);
      const loudness = Number.isFinite(v) ? Math.max(0, Math.min(100, v)) / 100 : 0;
      if (!enabled || !loudness) { this.stopMotor(); this.stopFanfare(); return; }
      if (this.fanfare) this.fanfare.volume = loudness;
      if (!active) {
        this.stopMotor();
        if (finished) this.playFanfare(loudness);
        else if (phase !== 'result') this.stopFanfare();
        return;
      }
      this.stopFanfare();
      const n = Number(score);
      const ratio = Number.isFinite(n) ? Math.max(0, Math.min(1, n / 9999)) : 0;
      if (!this.voice && (!ratio || this.failed)) return;
      if (!this.voice) {
        let ctx;
        try {
          ctx = this.createContext();
          const osc = ctx.createOscillator(), second = ctx.createOscillator(), rotor = ctx.createOscillator();
          const gain = ctx.createGain(), level = ctx.createGain(), secondLevel = ctx.createGain(), depth = ctx.createGain();
          const filter = ctx.createBiquadFilter();
          osc.type = 'sawtooth';
          second.type = 'square';
          second.detune.value = 7;
          rotor.type = 'sine';
          level.gain.value = 0.55;
          secondLevel.gain.value = 0.18;
          depth.gain.value = 0.22;
          filter.type = 'lowpass';
          filter.Q.value = 1.1;
          gain.gain.value = 0;
          osc.connect(level);
          second.connect(secondLevel);
          secondLevel.connect(level);
          rotor.connect(depth);
          depth.connect(level.gain);
          level.connect(filter);
          filter.connect(gain);
          gain.connect(ctx.destination);
          osc.start();
          second.start();
          rotor.start();
          this.voice = { ctx, osc, second, rotor, filter, gain, score: null, volume: null };
          // 외부 START 는 클릭 없이 들어오므로 Electron 창의 autoplayPolicy 와 함께 사용한다.
          if (ctx.state === 'suspended') {
            const voice = this.voice;
            ctx.resume().catch(() => {
              if (this.voice === voice) { this.failed = true; this.stop(); }
            });
          }
        } catch (_) {
          this.failed = true;
          if (ctx) ctx.close().catch(() => {});
          this.voice = null;
          return;
        }
      }
      const voice = this.voice;
      if (voice.score === ratio && voice.volume === loudness) return;
      voice.score = ratio;
      voice.volume = loudness;
      const t = voice.ctx.currentTime;
      const frequency = 90 * Math.pow(10, ratio);
      voice.osc.frequency.setTargetAtTime(frequency, t, 0.04);
      voice.second.frequency.setTargetAtTime(frequency, t, 0.04);
      voice.rotor.frequency.setTargetAtTime(14 + 65 * ratio, t, 0.04);
      voice.filter.frequency.setTargetAtTime(650 + 4200 * ratio, t, 0.04);
      voice.gain.gain.setTargetAtTime(ratio ? (0.4 + 0.2 * Math.sqrt(ratio)) * loudness : 0, t, 0.025);
    }

    playFanfare(volume) {
      if (!this.fanfare) return;
      try {
        this.fanfare.currentTime = 0;
        this.fanfare.volume = volume;
        const playing = this.fanfare.play();
        if (playing && playing.catch) playing.catch(() => {});
      } catch (_) { /* 소리 장치 오류가 게임을 중단하지 않게 한다 */ }
    }

    stopFanfare() {
      if (!this.fanfare || (this.fanfare.paused && !this.fanfare.currentTime)) return;
      try { this.fanfare.pause(); this.fanfare.currentTime = 0; } catch (_) { /* ignore */ }
    }

    stopMotor() {
      const voice = this.voice;
      if (!voice) return;
      this.voice = null;
      const t = voice.ctx.currentTime;
      voice.gain.gain.cancelScheduledValues(t);
      voice.gain.gain.setTargetAtTime(0, t, 0.01);
      voice.osc.stop(t + 0.05);
      voice.second.stop(t + 0.05);
      voice.rotor.stop(t + 0.05);
      // 소리 끝을 짧게 페이드한 뒤 장치를 해제한다.
      setTimeout(() => { voice.ctx.close().catch(() => {}); }, 80);
    }

    stop() {
      this.phase = null;
      this.stopMotor();
      this.stopFanfare();
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { GaugeSound };
  else root.GaugeSound = GaugeSound;
})(typeof window !== 'undefined' ? window : globalThis);
