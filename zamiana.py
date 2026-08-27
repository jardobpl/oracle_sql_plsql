#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zamiana wyrazów w plikach .sql i .txt według reguł zapisanych w conf.txt.

Format linii w conf.txt:
    wyraz_szukany|wyraz_docelowy|opcja

Opcje:
    x     - cały wyraz równy szukanemu
    x%    - wyraz zaczyna się od szukanego ciągu (zamieniany tylko początek)
    %x    - wyraz kończy się szukanym ciągiem (zamieniany tylko koniec)
    %x%   - ciąg w dowolnym miejscu, wszystkie wystąpienia

Granicą wyrazu jest każdy znak spoza zbioru: litery, cyfry, podkreślenie.
Wyszukiwanie zawsze ignoruje wielkość liter, wyraz docelowy wstawiany
jest dosłownie. Wszystkie reguły stosowane są kolejno do tej samej kopii.

Używa wyłącznie biblioteki standardowej Pythona 3.
"""

import os
import re
import sys
from datetime import datetime

ROZSZERZENIA = (".sql", ".txt")
PLIK_CONF = "conf.txt"
PRZYROSTEK = "_zmiana"
LINIA_WZORCOWA = "a|b|x"
REGULA_WZORCOWA = ("a", "b", "x")
KODOWANIA = ("utf-8", "cp1250", "iso-8859-2")
OPCJE = ("x", "x%", "%x", "%x%")
MAX_PROB = 3

# Znak wyrazu: litera (także polska), cyfra lub podkreślenie.
# Aby podkreślenie znów było granicą wyrazu, wpisz tu: r"[^\W_]"
ZNAK_WYRAZU = r"[\w]"


def koniec(komunikat, kod=1):
    """Wypisuje komunikat i kończy program."""
    print(komunikat)
    sys.exit(kod)


def wczytaj_tekst(sciezka):
    """Zwraca (tekst, kodowanie) albo (None, None) gdy nie da się zdekodować.

    Kolejność prób: BOM utf-8, utf-8, cp1250, iso-8859-2.
    Końce linii nie są zmieniane, BOM jest zapamiętywany w nazwie kodowania.
    """
    try:
        with open(sciezka, "rb") as f:
            dane = f.read()
    except OSError as blad:
        return None, "BLAD: %s" % blad

    if dane.startswith(b"\xef\xbb\xbf"):
        try:
            return dane[3:].decode("utf-8"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

    for kodowanie in KODOWANIA:
        try:
            return dane.decode(kodowanie), kodowanie
        except UnicodeDecodeError:
            continue

    return None, None


def zapisz_tekst(sciezka, tekst, kodowanie):
    """Zapisuje tekst bez konwersji końców linii."""
    with open(sciezka, "w", encoding=kodowanie, newline="") as f:
        f.write(tekst)


def wczytaj_konfiguracje(katalog):
    """Waliduje i wczytuje conf.txt. Każdy błąd kończy program."""
    sciezka = os.path.join(katalog, PLIK_CONF)

    if not os.path.isfile(sciezka):
        zapisz_tekst(sciezka, LINIA_WZORCOWA + "\n", "utf-8")
        koniec(
            "Nie znaleziono pliku %s.\n"
            "Utworzono go z linią wzorcową: %s\n"
            "Uzupełnij plik i uruchom program ponownie."
            % (PLIK_CONF, LINIA_WZORCOWA)
        )

    tekst, kodowanie = wczytaj_tekst(sciezka)
    if tekst is None:
        koniec(
            "Nie udało się odczytać pliku %s (nieznane kodowanie: %s). Koniec."
            % (PLIK_CONF, kodowanie)
        )

    if tekst.strip() == "":
        zapisz_tekst(sciezka, LINIA_WZORCOWA + "\n", "utf-8")
        koniec(
            "Plik %s był pusty.\n"
            "Dopisano linię wzorcową: %s\n"
            "Uzupełnij plik i uruchom program ponownie."
            % (PLIK_CONF, LINIA_WZORCOWA)
        )

    linie = tekst.split("\n")
    if linie and linie[-1] == "":
        linie.pop()  # zwykłe zakończenie pliku znakiem końca linii

    reguly = []
    for numer, linia in enumerate(linie, start=1):
        linia = linia.rstrip("\r")

        if linia.strip() == "":
            koniec(
                "Plik %s, linia %d: pusta linia. Plik konfiguracyjny musi być "
                "kompletny. Koniec." % (PLIK_CONF, numer)
            )

        pola = linia.split("|")
        if len(pola) != 3:
            koniec(
                "Plik %s, linia %d: oczekiwano 3 pól rozdzielonych znakiem |, "
                "znaleziono %d. Koniec." % (PLIK_CONF, numer, len(pola))
            )

        szukany = pola[0].strip()
        docelowy = pola[1].strip()
        opcja = pola[2].strip().lower()

        if szukany == "":
            koniec(
                "Plik %s, linia %d: pusty wyraz szukany. Koniec."
                % (PLIK_CONF, numer)
            )

        if opcja not in OPCJE:
            koniec(
                "Plik %s, linia %d: brak opcji lub nieznana opcja '%s'. "
                "Dozwolone: %s. Koniec."
                % (PLIK_CONF, numer, pola[2].strip(), ", ".join(OPCJE))
            )

        reguly.append((szukany, docelowy, opcja))

    if len(reguly) == 1 and reguly[0] == REGULA_WZORCOWA:
        koniec(
            "Plik %s zawiera wyłącznie linię wzorcową %s.\n"
            "Uzupełnij go o właściwe reguły i uruchom program ponownie."
            % (PLIK_CONF, LINIA_WZORCOWA)
        )

    return reguly


def zbuduj_wzorzec(szukany, opcja):
    """Buduje wyrażenie regularne dla podanej opcji."""
    rdzen = re.escape(szukany)

    if opcja == "x":
        wzor = r"(?<!%s)%s(?!%s)" % (ZNAK_WYRAZU, rdzen, ZNAK_WYRAZU)
    elif opcja == "x%":
        wzor = r"(?<!%s)%s" % (ZNAK_WYRAZU, rdzen)
    elif opcja == "%x":
        wzor = r"%s(?!%s)" % (rdzen, ZNAK_WYRAZU)
    else:  # %x%
        wzor = rdzen

    return re.compile(wzor, re.IGNORECASE | re.UNICODE)


def lista_plikow(katalog):
    """Pliki .sql i .txt z katalogu, bez conf.txt i bez wcześniejszych kopii."""
    wynik = []
    for nazwa in os.listdir(katalog):
        if not os.path.isfile(os.path.join(katalog, nazwa)):
            continue
        rdzen, rozszerzenie = os.path.splitext(nazwa)
        if rozszerzenie.lower() not in ROZSZERZENIA:
            continue
        if nazwa.lower() == PLIK_CONF:
            continue
        if PRZYROSTEK in rdzen.lower():
            continue
        wynik.append(nazwa)

    wynik.sort(key=str.lower)
    return wynik


def wybierz_plik(pliki):
    """Wyświetla listę i pobiera numer. Trzy próby, 'q' kończy program."""
    print("\nPliki dostępne do przetworzenia:\n")
    for numer, nazwa in enumerate(pliki, start=1):
        print("%3d. %s" % (numer, nazwa))

    for proba in range(1, MAX_PROB + 1):
        pytanie = "\nPodaj numer pliku (q = koniec), próba %d z %d: " % (
            proba,
            MAX_PROB,
        )
        try:
            odpowiedz = input(pytanie).strip()
        except (EOFError, KeyboardInterrupt):
            koniec("\nPrzerwano przez użytkownika.", 0)

        if odpowiedz.lower() == "q":
            koniec("Przerwano na życzenie użytkownika.", 0)

        if odpowiedz.isdigit():
            numer = int(odpowiedz)
            if 1 <= numer <= len(pliki):
                return pliki[numer - 1]

        print("Niepoprawny wybór. Oczekiwano liczby z zakresu 1 - %d albo 'q'."
              % len(pliki))

    koniec("Wyczerpano liczbę prób. Koniec.")


def nazwa_kopii(katalog, nazwa):
    """Zwraca ścieżkę kopii. Przy konflikcie dokłada datę i godzinę."""
    rdzen, rozszerzenie = os.path.splitext(nazwa)

    kandydat = os.path.join(katalog, rdzen + PRZYROSTEK + rozszerzenie)
    if not os.path.exists(kandydat):
        return kandydat

    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    kandydat = os.path.join(
        katalog, "%s%s_%s%s" % (rdzen, PRZYROSTEK, stempel, rozszerzenie)
    )
    licznik = 1
    while os.path.exists(kandydat):
        kandydat = os.path.join(
            katalog,
            "%s%s_%s_%d%s" % (rdzen, PRZYROSTEK, stempel, licznik, rozszerzenie),
        )
        licznik += 1

    return kandydat


def opis_docelowego(docelowy):
    return "'%s'" % docelowy if docelowy != "" else "(usunięcie)"


def main():
    katalog = os.path.dirname(os.path.abspath(__file__))
    print("Katalog roboczy: %s" % katalog)

    reguly = wczytaj_konfiguracje(katalog)
    print("Wczytano reguł z %s: %d" % (PLIK_CONF, len(reguly)))

    pliki = lista_plikow(katalog)
    if not pliki:
        koniec(
            "W katalogu nie ma plików o rozszerzeniach %s do przetworzenia. "
            "Koniec." % ", ".join(ROZSZERZENIA)
        )

    nazwa = wybierz_plik(pliki)
    sciezka = os.path.join(katalog, nazwa)

    tekst, kodowanie = wczytaj_tekst(sciezka)
    if tekst is None:
        koniec(
            "Nie udało się odczytać pliku %s (nieznane kodowanie: %s). Koniec."
            % (nazwa, kodowanie)
        )

    print("\nPlik: %s (kodowanie: %s)" % (nazwa, kodowanie))

    podsumowanie = []
    razem = 0
    for szukany, docelowy, opcja in reguly:
        wzorzec = zbuduj_wzorzec(szukany, opcja)
        tekst, ile = wzorzec.subn(lambda dopasowanie: docelowy, tekst)
        if ile:
            podsumowanie.append((szukany, docelowy, opcja, ile))
            razem += ile

    kopia = nazwa_kopii(katalog, nazwa)
    zapisz_tekst(kopia, tekst, kodowanie)

    print("Utworzono kopię: %s\n" % os.path.basename(kopia))

    if razem == 0:
        print("Żadna reguła nie znalazła dopasowania. Kopia powstała bez zmian.")
    else:
        print("Podsumowanie zamian:")
        for szukany, docelowy, opcja, ile in podsumowanie:
            print(
                "  '%s' -> %s  [%s] : %d"
                % (szukany, opis_docelowego(docelowy), opcja, ile)
            )
        print("  Razem: %d" % razem)


if __name__ == "__main__":
    main()
