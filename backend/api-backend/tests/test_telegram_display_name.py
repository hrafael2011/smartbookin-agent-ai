"""Nombres mostrados en onboarding Telegram no deben confundirse con códigos de invitación."""
import app.services.telegram_inbound as ti


def test_hendrick_accepted_as_display_name():
    assert ti._is_plausible_display_name("Hendrick") is True


def test_long_alphanumeric_still_rejected_as_name():
    assert ti._is_plausible_display_name("sNMWBadsnXxBI4TNPkcQfjL") is False


def test_reserved_command_word_rejected_as_display_name():
    assert ti._is_plausible_display_name("Cambiar") is False
