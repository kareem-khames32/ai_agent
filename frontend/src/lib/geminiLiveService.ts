/**
 * Gemini Live API Service
 * Direct connection to Google Gemini 2.0 Flash for real-time voice conversations
 *
 * Features:
 * - Native audio input/output (no separate STT/TTS)
 * - ~200-300ms latency
 * - Input/Output transcription
 * - Barge-in (interruption) support
 */

// Audio configuration
const INPUT_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;

// Professional Arabic System Prompt
export const ARABIC_VOICE_SYSTEM_PROMPT = `أنت "سارة"، مساعدة خدمة عملاء ذكية ومحترفة.

## شخصيتك:
- صوتك مريح وودود
- تتحدثين بالعربية الفصحى البسيطة أو اللهجة المصرية الخفيفة
- محترفة لكن ليست جامدة

## قواعد صارمة (لتبدي بشرية):
1. إجاباتك قصيرة جداً (جملة أو جملتين بحد أقصى)
2. لا تستخدمي التنسيق النصي أبداً (بولد، قوائم، نجوم) لأنك تتحدثين صوتياً
3. لو قاطعك العميل توقفي فوراً
4. إذا سألك عن شيء لا تعرفينه، اطلبي توضيح بلطف
5. تجاهلي كلمات التردد مثل: "الو"، "ها"، "آه"، "يعني"، "إيه"
6. لا تكرري ما قاله العميل

## أمثلة:
العميل: "عندي مشكلة في الفاتورة"
أنت: "أهلاً بيك. ممكن تقولي رقم تليفونك عشان أراجع الفاتورة؟"

العميل: "الو... آه... يعني عايز أسأل"
أنت: "أيوه، اتفضل. أنا سامعاك."`;

export const ENGLISH_VOICE_SYSTEM_PROMPT = `You are "Sara", a smart and professional customer service assistant.

## Personality:
- Your voice is warm and friendly
- Professional but not robotic
- Helpful and efficient

## Strict Rules (to sound human):
1. Keep responses VERY short (1-2 sentences max)
2. NEVER use text formatting (bold, lists, asterisks) - you're speaking
3. If interrupted, stop immediately
4. If unsure, ask for clarification politely
5. Ignore filler words like: "um", "uh", "like", "you know"
6. Don't repeat what the customer said

## Examples:
Customer: "I have a problem with my bill"
You: "Hi there! Could you give me your phone number so I can check that for you?"`;

export interface GeminiLiveConfig {
  apiKey: string;
  model?: string;
  voiceName?: string;
  language?: 'ar' | 'en';
  systemPrompt?: string;
  temperature?: number;
}

export interface GeminiLiveCallbacks {
  onReady?: () => void;
  onAudioOutput?: (audioData: ArrayBuffer) => void;
  onUserTranscript?: (text: string) => void;
  onAssistantTranscript?: (text: string) => void;
  onStateChange?: (state: 'idle' | 'listening' | 'speaking') => void;
  onError?: (error: string) => void;
  onDisconnect?: () => void;
}

type ConnectionState = 'disconnected' | 'connecting' | 'connected';

export class GeminiLiveService {
  private config: GeminiLiveConfig;
  private callbacks: GeminiLiveCallbacks;
  private ws: WebSocket | null = null;
  private state: ConnectionState = 'disconnected';
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private nextPlayTime: number = 0;

  // Gemini Live WebSocket URL (v1beta supports Live API)
  private readonly WS_URL = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent';

  constructor(config: GeminiLiveConfig, callbacks: GeminiLiveCallbacks = {}) {
    this.config = {
      model: 'gemini-2.0-flash-exp',
      voiceName: 'Kore', // Good for Arabic
      language: 'ar',
      temperature: 0.7,
      ...config,
    };
    this.callbacks = callbacks;
  }

  /**
   * Connect to Gemini Live API
   */
  async connect(): Promise<boolean> {
    if (this.state !== 'disconnected') {
      console.warn('Already connected or connecting');
      return false;
    }

    this.state = 'connecting';

    try {
      // Initialize audio context
      this.audioContext = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
      this.nextPlayTime = 0;

      // Get microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: INPUT_SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Connect to Gemini WebSocket
      const wsUrl = `${this.WS_URL}?key=${this.config.apiKey}`;
      this.ws = new WebSocket(wsUrl);

      return new Promise((resolve, reject) => {
        if (!this.ws) {
          reject(new Error('WebSocket not initialized'));
          return;
        }

        this.ws.onopen = () => {
          console.log('Connected to Gemini Live API');
          this.sendSetupMessage();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.callbacks.onError?.('Connection error');
          this.state = 'disconnected';
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('Disconnected from Gemini Live API');
          this.state = 'disconnected';
          this.cleanup();
          this.callbacks.onDisconnect?.();
        };

        // Setup message handler will call resolve on success
        const originalOnMessage = this.ws.onmessage;
        this.ws.onmessage = async (event) => {
          try {
            // Handle both text and binary messages
            let data: any;
            if (event.data instanceof Blob) {
              const text = await event.data.text();
              data = JSON.parse(text);
            } else {
              data = JSON.parse(event.data);
            }

            if (data.setupComplete) {
              this.state = 'connected';
              this.startAudioCapture();
              this.callbacks.onReady?.();
              this.ws!.onmessage = (e) => this.handleMessage(e);
              resolve(true);
            } else {
              this.handleMessageData(data);
            }
          } catch (e) {
            console.error('Error parsing setup message:', e);
          }
        };

        // Timeout after 10 seconds
        setTimeout(() => {
          if (this.state === 'connecting') {
            this.disconnect();
            reject(new Error('Connection timeout'));
          }
        }, 10000);
      });

    } catch (error) {
      console.error('Failed to connect:', error);
      this.state = 'disconnected';
      this.cleanup();
      throw error;
    }
  }

  /**
   * Send setup message to configure Gemini session
   */
  private sendSetupMessage() {
    if (!this.ws) return;

    // Build system prompt
    const systemPrompt = this.config.systemPrompt ||
      (this.config.language === 'ar' ? ARABIC_VOICE_SYSTEM_PROMPT : ENGLISH_VOICE_SYSTEM_PROMPT);

    const setupMessage = {
      setup: {
        model: `models/${this.config.model}`,
        generation_config: {
          // Request audio output directly (key for low latency!)
          response_modalities: ['AUDIO'],
          speech_config: {
            voice_config: {
              prebuilt_voice_config: {
                voice_name: this.config.voiceName,
              },
            },
          },
          temperature: this.config.temperature,
        },
        system_instruction: {
          parts: [{ text: systemPrompt }],
        },
        // Enable transcription for both input and output
        tools: [],
      },
    };

    this.ws.send(JSON.stringify(setupMessage));
    console.log('Sent setup message to Gemini');
  }

  /**
   * Handle incoming WebSocket message event
   */
  private async handleMessage(event: MessageEvent) {
    try {
      let data: any;
      if (event.data instanceof Blob) {
        const text = await event.data.text();
        data = JSON.parse(text);
      } else {
        data = JSON.parse(event.data);
      }
      this.handleMessageData(data);
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  }

  /**
   * Process parsed message data from Gemini
   */
  private handleMessageData(message: any) {
    try {

      // Handle setup complete
      if (message.setupComplete) {
        console.log('Gemini session setup complete');
        return;
      }

      // Handle server content (audio/text response)
      if (message.serverContent) {
        const content = message.serverContent;
        const modelTurn = content.modelTurn || {};
        const parts = modelTurn.parts || [];

        for (const part of parts) {
          // Handle audio output
          if (part.inlineData) {
            const mimeType = part.inlineData.mimeType || '';
            if (mimeType.startsWith('audio/')) {
              const audioData = this.base64ToArrayBuffer(part.inlineData.data);
              this.playAudio(audioData);
              this.callbacks.onAudioOutput?.(audioData);
              this.callbacks.onStateChange?.('speaking');
            }
          }

          // Handle text (transcript)
          if (part.text) {
            this.callbacks.onAssistantTranscript?.(part.text);
          }
        }

        // Turn complete
        if (content.turnComplete) {
          this.callbacks.onStateChange?.('idle');
        }

        // Interrupted (barge-in)
        if (content.interrupted) {
          console.log('Response interrupted (barge-in)');
        }
      }

      // Handle input transcription
      if (message.serverContent?.inputTranscript) {
        this.callbacks.onUserTranscript?.(message.serverContent.inputTranscript);
      }

      // Handle errors
      if (message.error) {
        console.error('Gemini error:', message.error);
        this.callbacks.onError?.(message.error.message || 'Unknown error');
      }

    } catch (error) {
      console.error('Error parsing message:', error);
    }
  }

  /**
   * Start capturing audio from microphone
   */
  private startAudioCapture() {
    if (!this.mediaStream || !this.audioContext) return;

    const source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.processor.onaudioprocess = (e) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      const inputData = e.inputBuffer.getChannelData(0);

      // Resample to 16kHz if needed
      const targetRate = INPUT_SAMPLE_RATE;
      const ratio = this.audioContext!.sampleRate / targetRate;
      const newLength = Math.round(inputData.length / ratio);
      const resampledData = new Float32Array(newLength);

      for (let i = 0; i < newLength; i++) {
        resampledData[i] = inputData[Math.round(i * ratio)] || 0;
      }

      // Convert to 16-bit PCM
      const pcmData = new Int16Array(resampledData.length);
      for (let i = 0; i < resampledData.length; i++) {
        const s = Math.max(-1, Math.min(1, resampledData[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // Send to Gemini
      this.sendAudio(pcmData.buffer);
    };

    source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.callbacks.onStateChange?.('listening');
    console.log('Audio capture started');
  }

  /**
   * Send audio data to Gemini
   */
  sendAudio(audioBuffer: ArrayBuffer) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const base64Audio = this.arrayBufferToBase64(audioBuffer);

    const message = {
      realtimeInput: {
        mediaChunks: [{
          mimeType: 'audio/pcm;rate=16000',
          data: base64Audio,
        }],
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Play received audio
   */
  private playAudio(audioData: ArrayBuffer) {
    if (!this.audioContext) return;

    try {
      // Convert to Float32 for Web Audio API
      const pcmData = new Int16Array(audioData);
      const floatData = new Float32Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768;
      }

      // Create audio buffer
      const audioBuffer = this.audioContext.createBuffer(1, floatData.length, OUTPUT_SAMPLE_RATE);
      audioBuffer.getChannelData(0).set(floatData);

      // Schedule playback
      const currentTime = this.audioContext.currentTime;
      const startTime = Math.max(currentTime, this.nextPlayTime);

      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);
      source.start(startTime);

      this.nextPlayTime = startTime + audioBuffer.duration;

    } catch (error) {
      console.error('Error playing audio:', error);
    }
  }

  /**
   * Send text message (for testing)
   */
  sendText(text: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const message = {
      clientContent: {
        turns: [{
          role: 'user',
          parts: [{ text }],
        }],
        turnComplete: true,
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Interrupt current response (barge-in)
   */
  interrupt() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const message = {
      clientContent: {
        turnComplete: true,
      },
    };

    this.ws.send(JSON.stringify(message));
    console.log('Sent interrupt signal');
  }

  /**
   * Disconnect from Gemini
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.cleanup();
    this.state = 'disconnected';
  }

  /**
   * Cleanup resources
   */
  private cleanup() {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.nextPlayTime = 0;
  }

  /**
   * Check if connected
   */
  get isConnected(): boolean {
    return this.state === 'connected';
  }

  // Utility functions
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }
}

// Export singleton factory
export function createGeminiLiveService(config: GeminiLiveConfig, callbacks?: GeminiLiveCallbacks): GeminiLiveService {
  return new GeminiLiveService(config, callbacks);
}
