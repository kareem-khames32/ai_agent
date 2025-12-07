"""
Voice AI Pipeline Test Script
Run this to test all components with your API keys
"""
import asyncio
import os
import sys
import base64
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.stt import STTService
from app.services.llm import LLMService, Message
from app.services.tts import TTSService
from app.services.pipeline import VoicePipeline, PipelineConfig


# ============================================
# ضع API Keys هنا
# ============================================

# STT - Speech to Text (اختر واحد)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "westeurope")

# LLM - Language Model (اختر واحد)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# TTS - Text to Speech (اختر واحد)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AZURE_TTS_KEY = os.getenv("AZURE_TTS_KEY", "")  # Same as AZURE_SPEECH_KEY usually
OPENAI_TTS_KEY = os.getenv("OPENAI_TTS_KEY", "")  # Same as OPENAI_API_KEY


def print_header(text: str):
    print("\n" + "=" * 50)
    print(f"  {text}")
    print("=" * 50)


def print_success(text: str):
    print(f"✅ {text}")


def print_error(text: str):
    print(f"❌ {text}")


def print_info(text: str):
    print(f"ℹ️  {text}")


async def test_llm():
    """Test LLM Service"""
    print_header("Testing LLM (Language Model)")

    # Determine which provider to use
    if ANTHROPIC_API_KEY:
        provider = "anthropic"
        api_key = ANTHROPIC_API_KEY
        print_info(f"Using Anthropic Claude")
    elif OPENAI_API_KEY:
        provider = "openai"
        api_key = OPENAI_API_KEY
        print_info(f"Using OpenAI GPT")
    elif GOOGLE_API_KEY:
        provider = "google"
        api_key = GOOGLE_API_KEY
        print_info(f"Using Google Gemini")
    else:
        print_error("No LLM API key configured!")
        return False

    try:
        llm = LLMService(provider=provider, api_key=api_key)

        # Test Arabic conversation
        response = await llm.generate(
            messages=[Message(role="user", content="مرحبا، كيف حالك؟")],
            system_prompt="أنت مساعد صوتي ذكي. تتحدث العربية. كن مختصراً.",
            max_tokens=100,
        )

        print_success(f"LLM Response: {response.text}")
        print_info(f"Tokens used: {response.usage}")
        return True

    except Exception as e:
        print_error(f"LLM Error: {e}")
        return False


async def test_tts():
    """Test TTS Service"""
    print_header("Testing TTS (Text to Speech)")

    # Determine which provider to use
    if ELEVENLABS_API_KEY:
        provider = "elevenlabs"
        api_key = ELEVENLABS_API_KEY
        region = None
        print_info(f"Using ElevenLabs")
    elif AZURE_TTS_KEY:
        provider = "azure"
        api_key = AZURE_TTS_KEY
        region = AZURE_SPEECH_REGION
        print_info(f"Using Azure TTS (Region: {region})")
    elif OPENAI_TTS_KEY:
        provider = "openai"
        api_key = OPENAI_TTS_KEY
        region = None
        print_info(f"Using OpenAI TTS")
    else:
        print_error("No TTS API key configured!")
        return False

    try:
        tts = TTSService(provider=provider, api_key=api_key, region=region)

        # Test Arabic speech
        text = "مرحبا بك في نظام الصوت الذكي"
        audio = await tts.synthesize(text)

        # Save to file
        output_file = Path(__file__).parent / "test_output.mp3"
        with open(output_file, "wb") as f:
            f.write(audio)

        print_success(f"TTS Generated: {len(audio)} bytes")
        print_success(f"Audio saved to: {output_file}")
        print_info("You can play this file to hear the result!")
        return True

    except Exception as e:
        print_error(f"TTS Error: {e}")
        return False


async def test_stt_with_generated_audio():
    """Test STT with the audio we just generated"""
    print_header("Testing STT (Speech to Text)")

    # Check if we have test audio
    audio_file = Path(__file__).parent / "test_output.mp3"
    if not audio_file.exists():
        print_info("No test audio file. Skipping STT test.")
        print_info("Run TTS test first to generate audio.")
        return None

    # Determine which provider to use
    if DEEPGRAM_API_KEY:
        provider = "deepgram"
        api_key = DEEPGRAM_API_KEY
        region = None
        print_info(f"Using Deepgram")
    elif AZURE_SPEECH_KEY:
        provider = "azure"
        api_key = AZURE_SPEECH_KEY
        region = AZURE_SPEECH_REGION
        print_info(f"Using Azure Speech (Region: {region})")
    else:
        print_error("No STT API key configured!")
        return False

    try:
        stt = STTService(provider=provider, api_key=api_key, region=region, language="ar")

        # Read audio file
        with open(audio_file, "rb") as f:
            audio_data = f.read()

        # Transcribe
        result = await stt.transcribe(audio_data, encoding="mp3")

        print_success(f"STT Result: {result.text}")
        print_info(f"Confidence: {result.confidence:.2%}")
        return True

    except Exception as e:
        print_error(f"STT Error: {e}")
        return False


async def test_full_pipeline():
    """Test full voice pipeline with text input"""
    print_header("Testing Full Pipeline (Text → LLM → TTS)")

    # Determine providers
    llm_provider = "anthropic" if ANTHROPIC_API_KEY else "openai" if OPENAI_API_KEY else "google" if GOOGLE_API_KEY else None
    llm_key = ANTHROPIC_API_KEY or OPENAI_API_KEY or GOOGLE_API_KEY

    tts_provider = "elevenlabs" if ELEVENLABS_API_KEY else "azure" if AZURE_TTS_KEY else "openai" if OPENAI_TTS_KEY else None
    tts_key = ELEVENLABS_API_KEY or AZURE_TTS_KEY or OPENAI_TTS_KEY

    stt_provider = "deepgram" if DEEPGRAM_API_KEY else "azure" if AZURE_SPEECH_KEY else None
    stt_key = DEEPGRAM_API_KEY or AZURE_SPEECH_KEY

    if not llm_provider or not tts_provider:
        print_error("Need at least LLM and TTS configured for pipeline test")
        return False

    print_info(f"Pipeline: STT({stt_provider or 'N/A'}) → LLM({llm_provider}) → TTS({tts_provider})")

    try:
        # Create pipeline config
        config = PipelineConfig(
            stt_provider=stt_provider or "deepgram",
            stt_api_key=stt_key,
            stt_region=AZURE_SPEECH_REGION,
            stt_language="ar",
            llm_provider=llm_provider,
            llm_api_key=llm_key,
            tts_provider=tts_provider,
            tts_api_key=tts_key,
            tts_region=AZURE_SPEECH_REGION,
            system_prompt="""أنت مساعد صوتي ذكي لشركة تحصيل ديون.
تتحدث باللغة العربية الفصحى.
كن مهذباً ومحترفاً.
ردودك يجب أن تكون مختصرة ومباشرة.""",
            max_tokens=150,
        )

        pipeline = VoicePipeline(config)

        # Simulate a text conversation (without STT)
        print_info("\nSimulating conversation...")

        # Add user message directly
        from app.services.llm import Message
        pipeline.messages.append(Message(role="user", content="مرحبا، أنا أحمد. عندي استفسار عن فاتورتي"))

        # Get LLM response
        response = await pipeline.llm.generate(
            messages=pipeline.messages,
            system_prompt=config.system_prompt,
            max_tokens=config.max_tokens,
        )

        print_success(f"\nUser: مرحبا، أنا أحمد. عندي استفسار عن فاتورتي")
        print_success(f"Assistant: {response.text}")

        # Generate audio
        audio = await pipeline.tts.synthesize(response.text)

        output_file = Path(__file__).parent / "conversation_response.mp3"
        with open(output_file, "wb") as f:
            f.write(audio)

        print_success(f"\nAudio response saved to: {output_file}")
        print_info("Play this file to hear the AI response!")

        return True

    except Exception as e:
        print_error(f"Pipeline Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def interactive_chat():
    """Interactive chat mode - type messages and get audio responses"""
    print_header("Interactive Chat Mode")
    print_info("Type your messages in Arabic and get audio responses")
    print_info("Type 'exit' to quit\n")

    # Determine providers
    llm_provider = "anthropic" if ANTHROPIC_API_KEY else "openai" if OPENAI_API_KEY else "google" if GOOGLE_API_KEY else None
    llm_key = ANTHROPIC_API_KEY or OPENAI_API_KEY or GOOGLE_API_KEY

    tts_provider = "elevenlabs" if ELEVENLABS_API_KEY else "azure" if AZURE_TTS_KEY else "openai" if OPENAI_TTS_KEY else None
    tts_key = ELEVENLABS_API_KEY or AZURE_TTS_KEY or OPENAI_TTS_KEY

    if not llm_provider or not tts_provider:
        print_error("Need LLM and TTS configured for interactive mode")
        return

    llm = LLMService(provider=llm_provider, api_key=llm_key)
    tts = TTSService(provider=tts_provider, api_key=tts_key, region=AZURE_SPEECH_REGION)

    messages = []
    system_prompt = """أنت مساعد صوتي ذكي لشركة تحصيل ديون.
تتحدث باللغة العربية.
كن مهذباً ومحترفاً ومختصراً."""

    response_count = 0

    while True:
        try:
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() == 'exit':
                print_info("Goodbye! مع السلامة!")
                break

            if not user_input:
                continue

            messages.append(Message(role="user", content=user_input))

            # Get response
            print("🤖 Assistant: ", end="", flush=True)
            response = await llm.generate(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=200,
            )

            print(response.text)
            messages.append(Message(role="assistant", content=response.text))

            # Generate audio
            audio = await tts.synthesize(response.text)
            response_count += 1
            output_file = Path(__file__).parent / f"response_{response_count}.mp3"
            with open(output_file, "wb") as f:
                f.write(audio)
            print_info(f"🔊 Audio saved: {output_file}")

        except KeyboardInterrupt:
            print("\n" + "=" * 50)
            print_info("Goodbye! مع السلامة!")
            break
        except Exception as e:
            print_error(f"Error: {e}")


async def main():
    print("\n" + "=" * 50)
    print("  🎤 Voice AI Pipeline Test Suite")
    print("=" * 50)

    print("\nConfigured API Keys:")
    print(f"  - Deepgram STT: {'✅' if DEEPGRAM_API_KEY else '❌'}")
    print(f"  - Azure Speech: {'✅' if AZURE_SPEECH_KEY else '❌'}")
    print(f"  - Anthropic LLM: {'✅' if ANTHROPIC_API_KEY else '❌'}")
    print(f"  - OpenAI LLM: {'✅' if OPENAI_API_KEY else '❌'}")
    print(f"  - Google LLM: {'✅' if GOOGLE_API_KEY else '❌'}")
    print(f"  - ElevenLabs TTS: {'✅' if ELEVENLABS_API_KEY else '❌'}")
    print(f"  - Azure TTS: {'✅' if AZURE_TTS_KEY else '❌'}")
    print(f"  - OpenAI TTS: {'✅' if OPENAI_TTS_KEY else '❌'}")

    print("\n" + "-" * 50)
    print("Choose test mode:")
    print("  1. Test LLM only")
    print("  2. Test TTS only")
    print("  3. Test STT only (needs audio file)")
    print("  4. Test Full Pipeline")
    print("  5. Interactive Chat (type & get audio)")
    print("  6. Run All Tests")
    print("-" * 50)

    choice = input("\nEnter choice (1-6): ").strip()

    if choice == "1":
        await test_llm()
    elif choice == "2":
        await test_tts()
    elif choice == "3":
        await test_stt_with_generated_audio()
    elif choice == "4":
        await test_full_pipeline()
    elif choice == "5":
        await interactive_chat()
    elif choice == "6":
        print("\nRunning all tests...")
        await test_llm()
        await test_tts()
        await test_stt_with_generated_audio()
        await test_full_pipeline()
    else:
        print_error("Invalid choice")

    print("\n" + "=" * 50)
    print("  Tests Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
