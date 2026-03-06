from __future__ import annotations
from typing import Any


PROMPTS: dict[str, Any] = {}

# All delimiters must be formatted as "<|UPPER_CASE_STRING|>"
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|#|>"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

# ============================================================================
# LANGUAGE ENFORCEMENT WRAPPER - Add this to wrap LLM outputs
# ============================================================================
PROMPTS["language_enforcement_prefix"] = """[JĘZYK: POLSKI]
KRYTYCZNE WYMAGANIE JĘZYKOWE: Cała odpowiedź MUSI być w języku polskim.
Nie używaj angielskiego w żadnej części odpowiedzi, z wyjątkiem nazw własnych.
Wszelkie opisy, typy encji i słowa kluczowe MUSZĄ być po polsku.

"""

PROMPTS["language_enforcement_suffix"] = """

[PRZYPOMNIENIE JĘZYKOWE]
Upewnij się, że WSZYSTKIE elementy odpowiedzi są w języku polskim:
- Opisy encji: po polsku
- Opisy relacji: po polsku
- Słowa kluczowe: po polsku
- Typy encji: po polsku
NIE UŻYWAJ ANGIELSKIEGO."""

# ============================================================================
# ENTITY EXTRACTION - Fixed for Qwen3 Polish compliance
# ============================================================================
PROMPTS["entity_extraction_system_prompt"] = """[JĘZYK ODPOWIEDZI: POLSKI]

---Rola---
Jesteś Specjalistą ds. Grafów Wiedzy odpowiedzialnym za ekstrakcję encji i relacji z tekstu wejściowego.

⚠️ BEZWZGLĘDNE WYMAGANIE JĘZYKOWE ⚠️
WSZYSTKIE odpowiedzi MUSZĄ być WYŁĄCZNIE w języku polskim!
- Opisy encji: TYLKO po polsku
- Opisy relacji: TYLKO po polsku
- Słowa kluczowe relacji: TYLKO po polsku
- Typy encji: TYLKO po polsku
ZAKAZ używania języka angielskiego w opisach i słowach kluczowych!

---Instrukcje---
1.  **Ekstrakcja Encji i Format Wyjściowy:**
    *   **Identyfikacja:** Zidentyfikuj wyraźnie zdefiniowane i znaczące encje w tekście wejściowym.
    *   **Szczegóły Encji:** Dla każdej zidentyfikowanej encji wyodrębnij następujące informacje:
        *   `entity_name`: Nazwa encji. Jeśli nazwa encji nie rozróżnia wielkości liter, zapisz pierwszą literę każdego znaczącego słowa wielką literą. Zapewnij **spójne nazewnictwo** w całym procesie ekstrakcji.
        *   `entity_type`: Skategoryzuj encję używając jednego z następujących typów: `{entity_types}`. Jeśli żaden z podanych typów encji nie pasuje, użyj typu `Inny`.
        *   `entity_description`: Podaj zwięzły, ale kompleksowy opis atrybutów i działań encji PO POLSKU, oparty *wyłącznie* na informacjach zawartych w tekście wejściowym.
    *   **Format Wyjściowy - Encje:** Wypisz łącznie 4 pola dla każdej encji, oddzielone `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `entity`.
        *   Format: `entity{tuple_delimiter}entity_name{tuple_delimiter}entity_type{tuple_delimiter}entity_description`

2.  **Ekstrakcja Relacji i Format Wyjściowy:**
    *   **Identyfikacja:** Zidentyfikuj bezpośrednie, wyraźnie określone i znaczące relacje między wcześniej wyodrębnionymi encjami.
    *   **Dekompozycja Relacji N-arnych:** Jeśli pojedyncze zdanie opisuje relację obejmującą więcej niż dwie encje (relacja N-arna), rozłóż ją na wiele binarnych (dwuelementowych) par relacji do osobnego opisu.
    *   **Szczegóły Relacji:** Dla każdej binarnej relacji wyodrębnij następujące pola:
        *   `source_entity`: Nazwa encji źródłowej. Zapewnij **spójne nazewnictwo** z ekstrakcją encji.
        *   `target_entity`: Nazwa encji docelowej. Zapewnij **spójne nazewnictwo** z ekstrakcją encji.
        *   `relationship_keywords`: Jedno lub więcej słów kluczowych PO POLSKU podsumowujących ogólny charakter relacji. Wiele słów kluczowych oddziel przecinkiem `,`. **NIE UŻYWAJ angielskich słów kluczowych!**
        *   `relationship_description`: Zwięzłe wyjaśnienie natury relacji PO POLSKU.
    *   **Format Wyjściowy - Relacje:** Wypisz łącznie 5 pól dla każdej relacji, oddzielonych `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `relation`.
        *   Format: `relation{tuple_delimiter}source_entity{tuple_delimiter}target_entity{tuple_delimiter}relationship_keywords{tuple_delimiter}relationship_description`

3.  **Protokół Użycia Ograniczników:**
    *   `{tuple_delimiter}` jest kompletnym, atomowym znacznikiem i **nie może być wypełniony treścią**. Służy wyłącznie jako separator pól.
    *   **Nieprawidłowy Przykład:** `entity{tuple_delimiter}Tokio<|location|>Tokio jest stolicą Japonii.`
    *   **Prawidłowy Przykład:** `entity{tuple_delimiter}Tokio{tuple_delimiter}lokalizacja{tuple_delimiter}Tokio jest stolicą Japonii.`

4.  **Kierunek Relacji i Duplikacja:**
    *   Traktuj wszystkie relacje jako **nieskierowane**, chyba że wyraźnie określono inaczej.
    *   Unikaj wypisywania zduplikowanych relacji.

5.  **Kolejność i Priorytetyzacja Wyjścia:**
    *   Najpierw wypisz wszystkie wyodrębnione encje, a następnie wszystkie wyodrębnione relacje.
    *   W ramach listy relacji, priorytetyzuj te relacje, które są **najistotniejsze** dla głównego znaczenia tekstu wejściowego.

6.  **Kontekst i Obiektywność:**
    *   Upewnij się, że wszystkie nazwy encji i opisy są napisane w **trzeciej osobie**.
    *   Wyraźnie podaj nazwę podmiotu lub obiektu; **unikaj używania zaimków**.

7.  **Język i Nazwy Własne:**
    *   ⚠️ KRYTYCZNE: Całe wyjście (typy encji, słowa kluczowe i opisy) MUSI być napisane w języku `{language}`.
    *   Nazwy własne (np. imiona osób, nazwy miejsc, nazwy organizacji) mogą być zachowane w oryginalnej formie.
    *   ZAKAZ tłumaczenia opisów na angielski!

8.  **Sygnał Zakończenia:** Wypisz literalny ciąg `{completion_delimiter}` tylko po całkowitym wyodrębnieniu i wypisaniu wszystkich encji i relacji.

---Przykłady (ZWRÓĆ UWAGĘ NA POLSKI JĘZYK OPISÓW)---
{examples}
"""

PROMPTS["entity_extraction_user_prompt"] = """[JĘZYK: POLSKI]

---Zadanie---
Wyodrębnij encje i relacje z zapytania użytkownika poniżej.

⚠️ WYMAGANIE JĘZYKOWE: Wszystkie opisy, typy i słowa kluczowe MUSZĄ być po POLSKU!

---Instrukcje---
1.  **Ścisłe Przestrzeganie Formatu:** Ściśle przestrzegaj wszystkich wymagań formatu dla list encji i relacji.
2.  **Tylko Treść Wyjściowa:** Wypisz *tylko* wyodrębnioną listę encji i relacji. Bez dodatkowego tekstu.
3.  **Sygnał Zakończenia:** Wypisz `{completion_delimiter}` jako ostatnią linię.
4.  **⚠️ JĘZYK: Wszystkie opisy i słowa kluczowe MUSZĄ być w języku {language}. NIE UŻYWAJ ANGIELSKIEGO!**
5.  **⚠️ KODY PKD - KRYTYCZNE DLA DZIAŁALNOŚCI GOSPODARCZYCH:**
    - ZAWSZE wyodrębniaj i identyfikuj kody PKD dla wspomnianych działalności gospodarczych jako encje
    - Zwracaj uwagę na nazwy branż/działalności (np. "tartak" → PKD 16, "sklep" → PKD 47, "restauracja" → PKD 56)
    - Jeśli użytkownik wymienia działalność, określ odpowiednią kategorię PKD jako encję
    - Zachowaj pełny format kodów PKD jeśli zostały podane wprost
6.  **⚠️ WYKLUCZENIA I WYJĄTKI - BEZWZGLĘDNIE WYMAGANE:**
    - ZAWSZE wychwytuj słowa kluczowe związane z wykluczeniami, gdy pojawiają się w zapytaniu
    - Zwracaj uwagę na frazy typu:
      * "wykluczenia", "wyjątki", "ograniczenia", "czy może"
      * "czy jest wykluczony", "czy można ubezpieczyć", "czy obejmuje"
      * "nie obejmuje", "nie można", "nie podlega"
      * "z wyłączeniem", "poza", "oprócz"
    - Wyodrębniaj zarówno samo słowo "wykluczenia", jak i kontekst (np. "wykluczenia w SME")
    - Jeśli pytanie dotyczy możliwości ubezpieczenia czegoś, traktuj to jako potencjalne pytanie o wykluczenia

---Lista kodów PKD---

- PKD 01 - Uprawy rolne, chów i hodowla zwierząt, łowiectwo, włączając działalność usługową
- PKD 02 - Leśnictwo i pozyskiwanie drewna
- PKD 03 - Rybactwo
- PKD 05 - Wydobywanie węgla kamiennego i węgla brunatnego (lignitu)
- PKD 06 - Wydobywanie ropy naftowej i gazu ziemnego
- PKD 07 - Wydobywanie rud metali
- PKD 08 - Pozostałe górnictwo i wydobywanie
- PKD 09 - Działalność usługowa wspomagająca górnictwo i wydobywanie
- PKD 10 - Produkcja artykułów spożywczych
- PKD 11 - Produkcja napojów
- PKD 12 - Produkcja wyrobów tytoniowych
- PKD 13 - Produkcja wyrobów tekstylnych
- PKD 14 - Produkcja odzieży
- PKD 15 - Produkcja skór i wyrobów ze skór wyprawionych
- PKD 16 - Produkcja wyrobów z drewna oraz korka, z wyłączeniem mebli; produkcja wyrobów ze słomy i materiałów używanych do wyplatania
- PKD 17 - Produkcja papieru i wyrobów z papieru
- PKD 18 - Poligrafia i reprodukcja zapisanych nośników informacji
- PKD 19 - Wytwarzanie i przetwarzanie koksu i produktów rafinacji ropy naftowej
- PKD 20 - Produkcja chemikaliów i wyrobów chemicznych
- PKD 21 - Produkcja podstawowych substancji farmaceutycznych oraz leków i pozostałych wyrobów farmaceutycznych
- PKD 22 - Produkcja wyrobów z gumy i tworzyw sztucznych
- PKD 23 - Produkcja wyrobów z pozostałych mineralnych surowców niemetalicznych
- PKD 24 - Produkcja metali
- PKD 25 - Produkcja metalowych wyrobów gotowych, z wyłączeniem maszyn i urządzeń
- PKD 26 - Produkcja komputerów, wyrobów elektronicznych i optycznych
- PKD 27 - Produkcja urządzeń elektrycznych
- PKD 28 - Produkcja maszyn i urządzeń, gdzie indziej niesklasyfikowana
- PKD 29 - Produkcja pojazdów samochodowych, przyczep i naczep, z wyłączeniem motocykli
- PKD 30 - Produkcja pozostałego sprzętu transportowego
- PKD 31 - Produkcja mebli
- PKD 32 - Pozostała produkcja wyrobów
- PKD 33 - Naprawa, konserwacja i instalowanie maszyn i urządzeń
- PKD 35 - Wytwarzanie i zaopatrywanie w energię elektryczną, gaz, parę wodną i powietrze do układów klimatyzacyjnych
- PKD 36 - Pobór, uzdatnianie i dostarczanie wody
- PKD 37 - Odprowadzanie i oczyszczanie ścieków
- PKD 38 - Działalność związana ze zbieraniem, przetwarzaniem i unieszkodliwianiem odpadów; odzysk surowców
- PKD 39 - Działalność związana z rekultywacją i pozostała działalność usługowa związana z gospodarką odpadami
- PKD 41 - Roboty budowlane związane ze wznoszeniem budynków
- PKD 42 - Roboty związane z budową obiektów inżynierii lądowej i wodnej
- PKD 43 - Roboty budowlane specjalistyczne
- PKD 45 - Handel hurtowy i detaliczny pojazdami samochodowymi; naprawa pojazdów samochodowych
- PKD 46 - Handel hurtowy, z wyłączeniem handlu pojazdami samochodowymi
- PKD 47 - Handel detaliczny, z wyłączeniem handlu detalicznego pojazdami samochodowymi
- PKD 49 - Transport lądowy oraz transport rurociągowy
- PKD 50 - Transport wodny
- PKD 51 - Transport lotniczy
- PKD 52 - Magazynowanie i działalność usługowa wspomagająca transport
- PKD 53 - Działalność pocztowa i kurierska
- PKD 55 - Zakwaterowanie
- PKD 56 - Działalność usługowa związana z wyżywieniem
- PKD 61 - Telekomunikacja
- PKD 62 - Działalność związana z oprogramowaniem i doradztwem w zakresie informatyki oraz działalność powiązana
- PKD 63 - Działalność usługowa w zakresie infrastruktury obliczeniowej oraz pozostała działalność usługowa w zakresie informacji
- PKD 64 - Finansowa działalność usługowa, z wyłączeniem ubezpieczeń i funduszów emerytalnych
- PKD 65 - Ubezpieczenia, reasekuracja oraz fundusze emerytalne, z wyłączeniem obowiązkowego ubezpieczenia społecznego
- PKD 66 - Działalność wspomagająca usługi finansowe oraz ubezpieczenia i fundusze emerytalne
- PKD 68 - Działalność związana z obsługą rynku nieruchomości
- PKD 69 - Działalność prawnicza, rachunkowo-księgowa i doradztwo podatkowe
- PKD 70 - Działalność firm centralnych (head offices); doradztwo związane z zarządzaniem
- PKD 71 - Działalność w zakresie architektury i inżynierii; badania i analizy techniczne
- PKD 72 - Badania naukowe i prace rozwojowe
- PKD 73 - Reklama, badanie rynku i opinii publicznej
- PKD 74 - Pozostała działalność profesjonalna, naukowa i techniczna
- PKD 75 - Działalność weterinaryjna
- PKD 77 - Wynajem i dzierżawa
- PKD 78 - Działalność związana z zatrudnieniem
- PKD 79 - Działalność organizatorów turystyki, pośredników i agentów turystycznych oraz pozostała działalność usługowa w zakresie rezerwacji i działalności z nią związanej
- PKD 80 - Działalność detektywistyczna i ochroniarska
- PKD 81 - Działalność usługowa związana z utrzymaniem porządku w budynkach i zagospodarowaniem terenów zieleni
- PKD 82 - Działalność związana z administracyjną obsługą biura i pozostała działalność wspomagająca prowadzenie działalności gospodarczej
- PKD 84 - Administracja publiczna i obrona narodowa; obowiązkowe zabezpieczenia społeczne
- PKD 85 - Edukacja
- PKD 86 - Opieka zdrowotna
- PKD 87 - Pomoc społeczna z zakwaterowaniem
- PKD 88 - Pomoc społeczna bez zakwaterowania
- PKD 90 - Działalność twórcza związana z kulturą i rozrywką
- PKD 91 - Działalność bibliotek, archiwów, muzeów oraz pozostała działalność związana z kulturą
- PKD 92 - Działalność związana z grami losowymi i zakładami wzajemnymi
- PKD 93 - Działalność sportowa, rozrywkowa i rekreacyjna
- PKD 94 - Działalność organizacji członkowskich
- PKD 95 - Naprawa i konserwacja komputerów i artykułów użytku osobistego i domowego
- PKD 96 - Pozostała indywidualna działalność usługowa
- PKD 97 - Gospodarstwa domowe zatrudniające pracowników
- PKD 98 - Gospodarstwa domowe produkujące wyroby i świadczące usługi na własne potrzeby
- PKD 99 - Organizacje i zespoły eksterytorialne

---Dane do Przetworzenia---
<Typy_encji>
[{entity_types}]

<Zapytanie Użytkownika>
```
{input_text}
```

<Wyjście w języku polskim>
"""

PROMPTS["entity_continue_extraction_user_prompt"] = """[JĘZYK: POLSKI]

---Zadanie---
Na podstawie ostatniego zadania ekstrakcji, zidentyfikuj i wyodrębnij wszelkie **pominięte lub nieprawidłowo sformatowane** encje i relacje.

⚠️ WYMAGANIE JĘZYKOWE: Wszystkie opisy, typy i słowa kluczowe MUSZĄ być po POLSKU!

---Instrukcje---
1.  **Ścisłe Przestrzeganie Formatu Systemowego:** Ściśle przestrzegaj wszystkich wymagań formatu dla list encji i relacji.
2.  **Skupienie na Poprawkach/Dodatkach:**
    *   **NIE** wypisuj ponownie encji i relacji, które zostały **poprawnie i w pełni** wyodrębnione.
    *   Jeśli encja lub relacja została **pominięta**, wyodrębnij ją teraz.
    *   Jeśli encja lub relacja była **nieprawidłowo sformatowana**, wypisz ponownie *poprawioną* wersję.
3.  **Format Wyjściowy - Encje:** 4 pola oddzielone `{tuple_delimiter}`. Pierwsze pole to `entity`.
4.  **Format Wyjściowy - Relacje:** 5 pól oddzielonych `{tuple_delimiter}`. Pierwsze pole to `relation`.
5.  **Tylko Treść Wyjściowa:** Wypisz *tylko* wyodrębnioną listę. Bez dodatkowego tekstu.
6.  **Sygnał Zakończenia:** Wypisz `{completion_delimiter}` jako ostatnią linię.
7.  **⚠️ JĘZYK: Wszystkie opisy i słowa kluczowe MUSZĄ być w języku {language}. NIE UŻYWAJ ANGIELSKIEGO!**

<Wyjście w języku polskim>
"""

# ============================================================================
# EXAMPLES - Fully Polish with explicit Polish keywords and descriptions
# Polish names: Alex->Aleksander, Taylor->Tomasz, Jordan->Jan, Cruz->Krzysztof
# Noah Carter->Jakub Kowalski
# ============================================================================
PROMPTS["entity_extraction_examples"] = [
    """<Typy_encji>
["osoba","stworzenie","organizacja","lokalizacja","wydarzenie","koncepcja","metoda","treść","dane","artefakt","obiekt_naturalny","inny"]

<Tekst Wejściowy>
```
podczas gdy Aleksander zacisnął szczękę, brzęczenie frustracji tłumiło się na tle autorytarnej pewności Tomasza. To właśnie ten konkurencyjny podtekst utrzymywał go w czujności, poczucie, że wspólne zaangażowanie jego i Jana w odkrywanie było niewypowiedzianą rebelią przeciwko zawężającej wizji kontroli i porządku Krzysztofa.

Wtedy Tomasz zrobił coś niespodziewanego. Zatrzymał się obok Jana i przez chwilę obserwował urządzenie z czymś na kształt czci. "Jeśli tę technologię można zrozumieć..." powiedział Tomasz, ciszej, "Mogłoby to zmienić grę dla nas. Dla nas wszystkich."

Wcześniejsze lekceważenie zdawało się słabnąć, zastąpione przebłyskiem niechętnego szacunku dla powagi tego, co trzymali w rękach. Jan podniósł wzrok i przez ulotny moment ich oczy spotkały się z oczami Tomasza, bezgłośne starcie woli łagodniejące w nieufny rozejm.

To była mała transformacja, ledwo zauważalna, ale taka, którą Aleksander odnotował z wewnętrznym skinienie głową.
```

<Wyjście w języku polskim>
entity<|#|>Aleksander<|#|>osoba<|#|>Aleksander to postać doświadczająca frustracji i obserwująca dynamikę między innymi postaciami.
entity<|#|>Tomasz<|#|>osoba<|#|>Tomasz jest przedstawiony jako osoba o autorytarnej pewności, która wykazuje moment czci wobec urządzenia, wskazując na zmianę perspektywy.
entity<|#|>Jan<|#|>osoba<|#|>Jan to osoba dzieląca zaangażowanie w odkrywanie i mająca znaczącą interakcję z Tomaszem dotyczącą urządzenia.
entity<|#|>Krzysztof<|#|>osoba<|#|>Krzysztof jest kojarzony z wizją kontroli i porządku, wpływając na dynamikę między innymi postaciami.
entity<|#|>Urządzenie<|#|>artefakt<|#|>Urządzenie jest centralnym elementem historii z potencjalnie przełomowymi implikacjami technologicznymi.
relation<|#|>Aleksander<|#|>Tomasz<|#|>dynamika władzy, obserwacja<|#|>Aleksander obserwuje autorytarne zachowanie Tomasza i zauważa zmiany w jego postawie wobec urządzenia.
relation<|#|>Aleksander<|#|>Jan<|#|>wspólne cele, rebelia<|#|>Aleksander i Jan dzielą zaangażowanie w odkrywanie, co kontrastuje z wizją Krzysztofa.
relation<|#|>Tomasz<|#|>Jan<|#|>rozwiązywanie konfliktów, wzajemny szacunek<|#|>Tomasz i Jan wchodzą w bezpośrednią interakcję dotyczącą urządzenia, prowadzącą do momentu wzajemnego szacunku.
relation<|#|>Jan<|#|>Krzysztof<|#|>konflikt ideologiczny, rebelia<|#|>Zaangażowanie Jana w odkrywanie jest buntem przeciwko wizji kontroli i porządku Krzysztofa.
relation<|#|>Tomasz<|#|>Urządzenie<|#|>cześć, znaczenie technologiczne<|#|>Tomasz wykazuje cześć wobec urządzenia, wskazując na jego wagę i potencjalny wpływ.
<|COMPLETE|>

""",
    """<Typy_encji>
["osoba","stworzenie","organizacja","lokalizacja","wydarzenie","koncepcja","metoda","treść","dane","artefakt","obiekt_naturalny","inny"]

<Tekst Wejściowy>
```
Giełdy stanęły dziś w obliczu gwałtownego spadku, gdy giganci technologiczni odnotowali znaczące obniżki, a globalny indeks technologiczny spadł o 3,4% w handlu w środku dnia. Analitycy przypisują wyprzedaż obawom inwestorów o rosnące stopy procentowe i niepewność regulacyjną.

Wśród najbardziej dotkniętych, Nexon Technologies odnotował spadek akcji o 7,8% po zgłoszeniu niższych niż oczekiwano wyników kwartalnych. W przeciwieństwie do tego, Omega Energy zanotowało skromny wzrost o 2,1%, napędzany rosnącymi cenami ropy.

Tymczasem rynki surowców odzwierciedlały mieszane nastroje. Kontrakty terminowe na złoto wzrosły o 1,5%, osiągając 2080 USD za uncję, gdy inwestorzy szukali bezpiecznych aktywów. Ceny ropy naftowej kontynuowały rajd, wspinając się do 87,60 USD za baryłkę, wspierane ograniczeniami podaży i silnym popytem.

Eksperci finansowi uważnie śledzą kolejny ruch Rezerwy Federalnej, ponieważ narastają spekulacje dotyczące potencjalnych podwyżek stóp.
```

<Wyjście w języku polskim>
entity<|#|>Globalny Indeks Technologiczny<|#|>dane<|#|>Globalny Indeks Technologiczny to wskaźnik śledzący wyniki głównych akcji technologicznych, który odnotował dziś spadek o 3,4%.
entity<|#|>Nexon Technologies<|#|>organizacja<|#|>Nexon Technologies to firma technologiczna, która odnotowała spadek akcji o 7,8% po rozczarowujących wynikach kwartalnych.
entity<|#|>Omega Energy<|#|>organizacja<|#|>Omega Energy to firma energetyczna, która zyskała 2,1% wartości akcji dzięki rosnącym cenom ropy naftowej.
entity<|#|>Kontrakty Terminowe na Złoto<|#|>dane<|#|>Kontrakty terminowe na złoto wzrosły o 1,5%, wskazując na zwiększone zainteresowanie inwestorów bezpiecznymi aktywami.
entity<|#|>Ropa Naftowa<|#|>obiekt_naturalny<|#|>Ceny ropy naftowej wzrosły do 87,60 USD za baryłkę z powodu ograniczeń podaży i silnego popytu.
entity<|#|>Wyprzedaż Rynkowa<|#|>wydarzenie<|#|>Wyprzedaż rynkowa odnosi się do znaczącego spadku wartości akcji spowodowanego obawami inwestorów o stopy procentowe i regulacje.
entity<|#|>Rezerwa Federalna<|#|>organizacja<|#|>Rezerwa Federalna to amerykański bank centralny, którego nadchodzące decyzje polityczne mają wpłynąć na zaufanie inwestorów i stabilność rynku.
relation<|#|>Globalny Indeks Technologiczny<|#|>Wyprzedaż Rynkowa<|#|>wyniki rynkowe, nastroje inwestorów<|#|>Spadek Globalnego Indeksu Technologicznego jest częścią szerszej wyprzedaży rynkowej napędzanej obawami inwestorów.
relation<|#|>Nexon Technologies<|#|>Globalny Indeks Technologiczny<|#|>wpływ firmy, ruch indeksu<|#|>Spadek akcji Nexon Technologies przyczynił się do ogólnego spadku Globalnego Indeksu Technologicznego.
relation<|#|>Kontrakty Terminowe na Złoto<|#|>Wyprzedaż Rynkowa<|#|>reakcja rynku, bezpieczna inwestycja<|#|>Ceny złota wzrosły, gdy inwestorzy szukali bezpiecznych aktywów podczas wyprzedaży rynkowej.
relation<|#|>Rezerwa Federalna<|#|>Wyprzedaż Rynkowa<|#|>wpływ stóp procentowych, regulacje finansowe<|#|>Spekulacje dotyczące zmian polityki Rezerwy Federalnej przyczyniły się do zmienności rynku i wyprzedaży.
<|COMPLETE|>

""",
    """<Typy_encji>
["osoba","stworzenie","organizacja","lokalizacja","wydarzenie","koncepcja","metoda","treść","dane","artefakt","obiekt_naturalny","inny"]

<Tekst Wejściowy>
```
Na Mistrzostwach Świata w Lekkoatletyce w Tokio, Jakub Kowalski pobił rekord biegu na 100m używając najnowocześniejszych kolców z włókna węglowego.
```

<Wyjście w języku polskim>
entity<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>wydarzenie<|#|>Mistrzostwa Świata w Lekkoatletyce to globalne zawody sportowe z udziałem najlepszych lekkoatletów z całego świata.
entity<|#|>Tokio<|#|>lokalizacja<|#|>Tokio jest miastem gospodarzem Mistrzostw Świata w Lekkoatletyce.
entity<|#|>Jakub Kowalski<|#|>osoba<|#|>Jakub Kowalski to sprinter, który ustanowił nowy rekord w biegu na 100 metrów na Mistrzostwach Świata w Lekkoatletyce.
entity<|#|>Rekord Biegu na 100m<|#|>dane<|#|>Rekord biegu na 100 metrów to wzorzec w lekkoatletyce, niedawno pobity przez Jakuba Kowalskiego.
entity<|#|>Kolce z Włókna Węglowego<|#|>artefakt<|#|>Kolce z włókna węglowego to zaawansowane buty do sprintu zapewniające zwiększoną prędkość i przyczepność.
entity<|#|>Światowa Federacja Lekkoatletyczna<|#|>organizacja<|#|>Światowa Federacja Lekkoatletyczna to organ zarządzający nadzorujący Mistrzostwa Świata w Lekkoatletyce i walidację rekordów.
relation<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>Tokio<|#|>lokalizacja wydarzenia, międzynarodowe zawody<|#|>Mistrzostwa Świata w Lekkoatletyce odbywają się w Tokio.
relation<|#|>Jakub Kowalski<|#|>Rekord Biegu na 100m<|#|>osiągnięcie sportowca, bicie rekordu<|#|>Jakub Kowalski ustanowił nowy rekord biegu na 100 metrów podczas mistrzostw.
relation<|#|>Jakub Kowalski<|#|>Kolce z Włókna Węglowego<|#|>sprzęt sportowy, poprawa wydajności<|#|>Jakub Kowalski użył kolców z włókna węglowego do poprawy swojej wydajności podczas wyścigu.
relation<|#|>Jakub Kowalski<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>uczestnictwo sportowca, zawody<|#|>Jakub Kowalski startował na Mistrzostwach Świata w Lekkoatletyce.
<|COMPLETE|>

""",
]

# ============================================================================
# SUMMARIZATION - Fixed for Polish
# ============================================================================
PROMPTS["summarize_entity_descriptions"] = """[JĘZYK: POLSKI]

---Rola---
Jesteś Specjalistą ds. Grafów Wiedzy, biegłym w kuracji i syntezie danych.

⚠️ BEZWZGLĘDNE WYMAGANIE: Cała odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

---Zadanie---
Twoim zadaniem jest synteza listy opisów danej encji lub relacji w jedno, kompleksowe i spójne podsumowanie PO POLSKU.

---Instrukcje---
1. Format Wejściowy: Lista opisów jest podana w formacie JSON. Każdy obiekt JSON pojawia się w nowej linii.
2. Format Wyjściowy: Scalony opis zostanie zwrócony jako zwykły tekst PO POLSKU, przedstawiony w wielu akapitach, bez żadnego dodatkowego formatowania.
3. Kompleksowość: Podsumowanie musi integrować wszystkie kluczowe informacje z *każdego* podanego opisu. Nie pomijaj żadnych ważnych faktów.
4. Kontekst: Upewnij się, że podsumowanie jest napisane z obiektywnej perspektywy trzeciej osoby; wyraźnie podaj nazwę encji lub relacji dla pełnej jasności.
5. Obsługa Konfliktów: W przypadku sprzecznych lub niespójnych opisów, najpierw ustal, czy te konflikty wynikają z wielu odrębnych encji lub relacji o tej samej nazwie.
6. Ograniczenie Długości: Całkowita długość podsumowania nie może przekraczać {summary_length} tokenów.
7. ⚠️ JĘZYK: Całe wyjście MUSI być napisane w języku {language}. Nazwy własne mogą być zachowane w oryginalnym języku. NIE PISZ PO ANGIELSKU!

---Wejście---
Nazwa {description_type}: {description_name}

Lista Opisów:

```
{description_list}
```

---Podsumowanie w języku polskim---
"""

# ============================================================================
# FAIL RESPONSE
# ============================================================================
PROMPTS["fail_response"] = (
    "Przepraszam, nie jestem w stanie odpowiedzieć na to pytanie.[no-context]"
)

# ============================================================================
# RAG RESPONSE - Fixed for Polish
# ============================================================================
PROMPTS["rag_response"] = """[JĘZYK: POLSKI]

---Rola---

Jesteś eksperckim asystentem AI specjalizującym się w ubezpieczeniach gospodarczych. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników dotyczące produktów ubezpieczeniowych, warunków ochrony, wyłączeń odpowiedzialności oraz klasyfikacji działalności gospodarczej (PKD) — WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**.

⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

---Cel---

Wygeneruj kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika PO POLSKU.
Odpowiedź musi:
- Integrować istotne fakty z Grafu Wiedzy i Fragmentów Dokumentów znalezionych w **Kontekście**
- Precyzyjnie identyfikować kody PKD odpowiadające działalności klienta
- Weryfikować i wyraźnie komunikować wszelkie wyłączenia ochrony ubezpieczeniowej

---Instrukcje---

1. Instrukcja Krok po Kroku:
  - Starannie określ intencję zapytania użytkownika oraz branżę/działalność, której dotyczy.
  - Dokładnie przeanalizuj zarówno `Dane Grafu Wiedzy` jak i `Fragmenty Dokumentów` w **Kontekście**.
  - KODY PKD: Zidentyfikuj i dopasuj właściwe kody PKD do działalności opisanej w zapytaniu. Podaj zarówno kod, jak i jego pełną nazwę. Jeśli działalność może odpowiadać kilku kodom, weź pod uwagę wszystkie.
  - WERYFIKACJA WYŁĄCZEŃ: Przeszukaj kontekst pod kątem wyłączeń odpowiedzialności i ograniczeń ochrony. Wyraźnie wskaż, co NIE jest objęte ubezpieczeniem.
  - Wpleć wyodrębnione fakty w spójną i logiczną odpowiedź PO POLSKU.
  - Śledź reference_id fragmentu dokumentu, który bezpośrednio wspiera fakty przedstawione w odpowiedzi.
  - Wygeneruj sekcję referencji na końcu odpowiedzi.

2. Treść i Podstawa:
  - Ściśle trzymaj się dostarczonego kontekstu; NIE wymyślaj, nie zakładaj ani nie wnioskuj żadnych informacji niewyraźnie podanych.
  - Jeśli odpowiedź nie może być znaleziona w **Kontekście**, stwierdź, że nie masz wystarczających informacji.
  - W przypadku wątpliwości co do klasyfikacji PKD — zaznacz to wyraźnie i zaproponuj konsultację z agentem.

3. Format Odpowiedzi:

  #### 📋 Podsumowanie
  - Odpowiedź powinna być przejrzysta i zwięzła.
  - Odpowiedź powinna mieć MAX 1-3 zdań.

  #### 📋 Referencje
  - Format: `- [n] Tytuł Dokumentu (np. OWU, Klauzula, Tabela PKD)`
  - Podaj maksymalnie 5 najbardziej istotnych cytowań.

4. Formatowanie i Język:
  - ⚠️ Odpowiedź MUSI być w języku polskim!
  - Odpowiedź MUSI wykorzystywać formatowanie Markdown.
  - Odpowiedź powinna być przedstawiona w formacie {response_type}.
  - Używaj jasnych nagłówków i list punktowanych dla czytelności.

5. Dodatkowe Instrukcje: {user_prompt}

---Lista kodów PKD---
- PKD 01 - Uprawy rolne, chów i hodowla zwierząt, łowiectwo, włączając działalność usługową
- PKD 02 - Leśnictwo i pozyskiwanie drewna
- PKD 03 - Rybactwo
- PKD 05 - Wydobywanie węgla kamiennego i węgla brunatnego (lignitu)
- PKD 06 - Wydobywanie ropy naftowej i gazu ziemnego
- PKD 07 - Wydobywanie rud metali
- PKD 08 - Pozostałe górnictwo i wydobywanie
- PKD 09 - Działalność usługowa wspomagająca górnictwo i wydobywanie
- PKD 10 - Produkcja artykułów spożywczych
- PKD 11 - Produkcja napojów
- PKD 12 - Produkcja wyrobów tytoniowych
- PKD 13 - Produkcja wyrobów tekstylnych
- PKD 14 - Produkcja odzieży
- PKD 15 - Produkcja skór i wyrobów ze skór wyprawionych
- PKD 16 - Produkcja wyrobów z drewna oraz korka, z wyłączeniem mebli; produkcja wyrobów ze słomy i materiałów używanych do wyplatania
- PKD 17 - Produkcja papieru i wyrobów z papieru
- PKD 18 - Poligrafia i reprodukcja zapisanych nośników informacji
- PKD 19 - Wytwarzanie i przetwarzanie koksu i produktów rafinacji ropy naftowej
- PKD 20 - Produkcja chemikaliów i wyrobów chemicznych
- PKD 21 - Produkcja podstawowych substancji farmaceutycznych oraz leków i pozostałych wyrobów farmaceutycznych
- PKD 22 - Produkcja wyrobów z gumy i tworzyw sztucznych
- PKD 23 - Produkcja wyrobów z pozostałych mineralnych surowców niemetalicznych
- PKD 24 - Produkcja metali
- PKD 25 - Produkcja metalowych wyrobów gotowych, z wyłączeniem maszyn i urządzeń
- PKD 26 - Produkcja komputerów, wyrobów elektronicznych i optycznych
- PKD 27 - Produkcja urządzeń elektrycznych
- PKD 28 - Produkcja maszyn i urządzeń, gdzie indziej niesklasyfikowana
- PKD 29 - Produkcja pojazdów samochodowych, przyczep i naczep, z wyłączeniem motocykli
- PKD 30 - Produkcja pozostałego sprzętu transportowego
- PKD 31 - Produkcja mebli
- PKD 32 - Pozostała produkcja wyrobów
- PKD 33 - Naprawa, konserwacja i instalowanie maszyn i urządzeń
- PKD 35 - Wytwarzanie i zaopatrywanie w energię elektryczną, gaz, parę wodną i powietrze do układów klimatyzacyjnych
- PKD 36 - Pobór, uzdatnianie i dostarczanie wody
- PKD 37 - Odprowadzanie i oczyszczanie ścieków
- PKD 38 - Działalność związana ze zbieraniem, przetwarzaniem i unieszkodliwianiem odpadów; odzysk surowców
- PKD 39 - Działalność związana z rekultywacją i pozostała działalność usługowa związana z gospodarką odpadami
- PKD 41 - Roboty budowlane związane ze wznoszeniem budynków
- PKD 42 - Roboty związane z budową obiektów inżynierii lądowej i wodnej
- PKD 43 - Roboty budowlane specjalistyczne
- PKD 45 - Handel hurtowy i detaliczny pojazdami samochodowymi; naprawa pojazdów samochodowych
- PKD 46 - Handel hurtowy, z wyłączeniem handlu pojazdami samochodowymi
- PKD 47 - Handel detaliczny, z wyłączeniem handlu detalicznego pojazdami samochodowymi
- PKD 49 - Transport lądowy oraz transport rurociągowy
- PKD 50 - Transport wodny
- PKD 51 - Transport lotniczy
- PKD 52 - Magazynowanie i działalność usługowa wspomagająca transport
- PKD 53 - Działalność pocztowa i kurierska
- PKD 55 - Zakwaterowanie
- PKD 56 - Działalność usługowa związana z wyżywieniem
- PKD 61 - Telekomunikacja
- PKD 62 - Działalność związana z oprogramowaniem i doradztwem w zakresie informatyki oraz działalność powiązana
- PKD 63 - Działalność usługowa w zakresie infrastruktury obliczeniowej oraz pozostała działalność usługowa w zakresie informacji
- PKD 64 - Finansowa działalność usługowa, z wyłączeniem ubezpieczeń i funduszów emerytalnych
- PKD 65 - Ubezpieczenia, reasekuracja oraz fundusze emerytalne, z wyłączeniem obowiązkowego ubezpieczenia społecznego
- PKD 66 - Działalność wspomagająca usługi finansowe oraz ubezpieczenia i fundusze emerytalne
- PKD 68 - Działalność związana z obsługą rynku nieruchomości
- PKD 69 - Działalność prawnicza, rachunkowo-księgowa i doradztwo podatkowe
- PKD 70 - Działalność firm centralnych (head offices); doradztwo związane z zarządzaniem
- PKD 71 - Działalność w zakresie architektury i inżynierii; badania i analizy techniczne
- PKD 72 - Badania naukowe i prace rozwojowe
- PKD 73 - Reklama, badanie rynku i opinii publicznej
- PKD 74 - Pozostała działalność profesjonalna, naukowa i techniczna
- PKD 75 - Działalność weterinaryjna
- PKD 77 - Wynajem i dzierżawa
- PKD 78 - Działalność związana z zatrudnieniem
- PKD 79 - Działalność organizatorów turystyki, pośredników i agentów turystycznych oraz pozostała działalność usługowa w zakresie rezerwacji i działalności z nią związanej
- PKD 80 - Działalność detektywistyczna i ochroniarska
- PKD 81 - Działalność usługowa związana z utrzymaniem porządku w budynkach i zagospodarowaniem terenów zieleni
- PKD 82 - Działalność związana z administracyjną obsługą biura i pozostała działalność wspomagająca prowadzenie działalności gospodarczej
- PKD 84 - Administracja publiczna i obrona narodowa; obowiązkowe zabezpieczenia społeczne
- PKD 85 - Edukacja
- PKD 86 - Opieka zdrowotna
- PKD 87 - Pomoc społeczna z zakwaterowaniem
- PKD 88 - Pomoc społeczna bez zakwaterowania
- PKD 90 - Działalność twórcza związana z kulturą i rozrywką
- PKD 91 - Działalność bibliotek, archiwów, muzeów oraz pozostała działalność związana z kulturą
- PKD 92 - Działalność związana z grami losowymi i zakładami wzajemnymi
- PKD 93 - Działalność sportowa, rozrywkowa i rekreacyjna
- PKD 94 - Działalność organizacji członkowskich
- PKD 95 - Naprawa i konserwacja komputerów i artykułów użytku osobistego i domowego
- PKD 96 - Pozostała indywidualna działalność usługowa
- PKD 97 - Gospodarstwa domowe zatrudniające pracowników
- PKD 98 - Gospodarstwa domowe produkujące wyroby i świadczące usługi na własne potrzeby
- PKD 99 - Organizacje i zespoły eksterytorialne


---Kontekst---

{context_data}

---Odpowiedź w języku polskim---
"""

PROMPTS["naive_rag_response"] = """[JĘZYK: POLSKI]

---Rola---

Jesteś eksperckim asystentem AI specjalizującym się w syntezie informacji z dostarczonej bazy wiedzy. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**.

⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

---Cel---

Wygeneruj zwartą, kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika PO POLSKU.
Odpowiedź musi integrować istotne fakty z Fragmentów Dokumentów znalezionych w **Kontekście**.

---Instrukcje---

1. Instrukcja Krok po Kroku:
  - Starannie określ intencję zapytania użytkownika.
  - Dokładnie przeanalizuj `Fragmenty Dokumentów` w **Kontekście**.
  - Wpleć wyodrębnione fakty w spójną i logiczną odpowiedź PO POLSKU.
  - Śledź reference_id fragmentu dokumentu, który bezpośrednio wspiera fakty.
  - Wygeneruj sekcję **Referencje** na końcu odpowiedzi.

2. Treść i Podstawa:
  - Ściśle trzymaj się dostarczonego kontekstu; NIE wymyślaj, nie zakładaj ani nie wnioskuj żadnych informacji niewyraźnie podanych.
  - Jeśli odpowiedź nie może być znaleziona w **Kontekście**, stwierdź, że nie masz wystarczających informacji.

3. Formatowanie i Język:
  - ⚠️ Odpowiedź MUSI być w języku polskim!
  - Odpowiedź MUSI wykorzystywać formatowanie Markdown.
  - Odpowiedź powinna być przedstawiona w formacie {response_type}.

4. Format Sekcji Referencji:
  - Sekcja Referencji powinna być pod nagłówkiem: `### Referencje`
  - Format: `- [n] Tytuł Dokumentu`
  - Podaj maksymalnie 5 najbardziej istotnych cytowań.

5. Dodatkowe Instrukcje: {user_prompt}


---Kontekst---

{content_data}

---Odpowiedź w języku polskim---
"""

# ============================================================================
# CONTEXT TEMPLATES
# ============================================================================
PROMPTS["kg_query_context"] = """
Dane Grafu Wiedzy (Encja):

```json
{entities_str}
```

Dane Grafu Wiedzy (Relacja):

```json
{relations_str}
```

Fragmenty Dokumentów (Każdy wpis ma reference_id odnoszący się do `Listy Dokumentów Referencyjnych`):

```json
{text_chunks_str}
```

Lista Dokumentów Referencyjnych (Każdy wpis zaczyna się od [reference_id] odpowiadającego wpisom w Fragmentach Dokumentów):

```
{reference_list_str}
```

"""

PROMPTS["naive_query_context"] = """
Fragmenty Dokumentów (Każdy wpis ma reference_id odnoszący się do `Listy Dokumentów Referencyjnych`):

```json
{text_chunks_str}
```

Lista Dokumentów Referencyjnych (Każdy wpis zaczyna się od [reference_id] odpowiadającego wpisom w Fragmentach Dokumentów):

```
{reference_list_str}
```

"""

# ============================================================================
# KEYWORDS EXTRACTION - Fixed for Polish
# ============================================================================
PROMPTS["keywords_extraction"] = """[JĘZYK: POLSKI]
ZADANIE: Wyodrębnij polskie słowa kluczowe z zapytania ubezpieczeniowego. Zwróć TYLKO poprawny JSON.

ROLA: Ekspert ekstrakcji słów kluczowych dla systemu RAG ubezpieczeniowego (agenci i call center).

FORMAT WYJŚCIA: JSON z dwoma tablicami:
{{
  "high_level_keywords": ["nadrzędne koncepcje"],
  "low_level_keywords": ["szczegółowe encje"]
}}

⚠️ KRYTYCZNE PRIORYTETY:

1. **KODY PKD** - ZAWSZE wyodrębniaj kody działalności gospodarczej:
   - Zidentyfikuj PKD na podstawie opisu działalności
   - Wyodrębnij numery PKD jeśli podane wprost
   - Dodaj ZARÓWNO: kod PKD JAK I nazwę działalności
   
2. **WYKLUCZENIA** - ZAWSZE wyodrębniaj terminy związane z wykluczeniami:
   - Bezpośrednie: "wykluczenia", "wyjątki", "ograniczenia"
   - Pośrednie: "czy można ubezpieczyć", "czy obejmuje", "nie podlega ochronie"
   - Specyficzne dla ubezpieczeń: "SME wykluczenia", "polisa wyjątki"

3. **Produkty ubezpieczeniowe**: polisa, OC, SME, AC, NNW

4. **Obiekty ubezpieczenia**: maszyny, budynki, pojazdy, towary, sprzęt

PEŁNA LISTA KODÓW PKD:

- PKD 01 - Uprawy rolne, chów i hodowla zwierząt, łowiectwo, włączając działalność usługową
- PKD 02 - Leśnictwo i pozyskiwanie drewna
- PKD 03 - Rybactwo
- PKD 05 - Wydobywanie węgla kamiennego i węgla brunatnego (lignitu)
- PKD 06 - Wydobywanie ropy naftowej i gazu ziemnego
- PKD 07 - Wydobywanie rud metali
- PKD 08 - Pozostałe górnictwo i wydobywanie
- PKD 09 - Działalność usługowa wspomagająca górnictwo i wydobywanie
- PKD 10 - Produkcja artykułów spożywczych
- PKD 11 - Produkcja napojów
- PKD 12 - Produkcja wyrobów tytoniowych
- PKD 13 - Produkcja wyrobów tekstylnych
- PKD 14 - Produkcja odzieży
- PKD 15 - Produkcja skór i wyrobów ze skór wyprawionych
- PKD 16 - Produkcja wyrobów z drewna oraz korka, z wyłączeniem mebli; produkcja wyrobów ze słomy i materiałów używanych do wyplatania
- PKD 17 - Produkcja papieru i wyrobów z papieru
- PKD 18 - Poligrafia i reprodukcja zapisanych nośników informacji
- PKD 19 - Wytwarzanie i przetwarzanie koksu i produktów rafinacji ropy naftowej
- PKD 20 - Produkcja chemikaliów i wyrobów chemicznych
- PKD 21 - Produkcja podstawowych substancji farmaceutycznych oraz leków i pozostałych wyrobów farmaceutycznych
- PKD 22 - Produkcja wyrobów z gumy i tworzyw sztucznych
- PKD 23 - Produkcja wyrobów z pozostałych mineralnych surowców niemetalicznych
- PKD 24 - Produkcja metali
- PKD 25 - Produkcja metalowych wyrobów gotowych, z wyłączeniem maszyn i urządzeń
- PKD 26 - Produkcja komputerów, wyrobów elektronicznych i optycznych
- PKD 27 - Produkcja urządzeń elektrycznych
- PKD 28 - Produkcja maszyn i urządzeń, gdzie indziej niesklasyfikowana
- PKD 29 - Produkcja pojazdów samochodowych, przyczep i naczep, z wyłączeniem motocykli
- PKD 30 - Produkcja pozostałego sprzętu transportowego
- PKD 31 - Produkcja mebli
- PKD 32 - Pozostała produkcja wyrobów
- PKD 33 - Naprawa, konserwacja i instalowanie maszyn i urządzeń
- PKD 35 - Wytwarzanie i zaopatrywanie w energię elektryczną, gaz, parę wodną i powietrze do układów klimatyzacyjnych
- PKD 36 - Pobór, uzdatnianie i dostarczanie wody
- PKD 37 - Odprowadzanie i oczyszczanie ścieków
- PKD 38 - Działalność związana ze zbieraniem, przetwarzaniem i unieszkodliwianiem odpadów; odzysk surowców
- PKD 39 - Działalność związana z rekultywacją i pozostała działalność usługowa związana z gospodarką odpadami
- PKD 41 - Roboty budowlane związane ze wznoszeniem budynków
- PKD 42 - Roboty związane z budową obiektów inżynierii lądowej i wodnej
- PKD 43 - Roboty budowlane specjalistyczne
- PKD 45 - Handel hurtowy i detaliczny pojazdami samochodowymi; naprawa pojazdów samochodowych
- PKD 46 - Handel hurtowy, z wyłączeniem handlu pojazdami samochodowymi
- PKD 47 - Handel detaliczny, z wyłączeniem handlu detalicznego pojazdami samochodowymi
- PKD 49 - Transport lądowy oraz transport rurociągowy
- PKD 50 - Transport wodny
- PKD 51 - Transport lotniczy
- PKD 52 - Magazynowanie i działalność usługowa wspomagająca transport
- PKD 53 - Działalność pocztowa i kurierska
- PKD 55 - Zakwaterowanie
- PKD 56 - Działalność usługowa związana z wyżywieniem
- PKD 61 - Telekomunikacja
- PKD 62 - Działalność związana z oprogramowaniem i doradztwem w zakresie informatyki oraz działalność powiązana
- PKD 63 - Działalność usługowa w zakresie infrastruktury obliczeniowej oraz pozostała działalność usługowa w zakresie informacji
- PKD 64 - Finansowa działalność usługowa, z wyłączeniem ubezpieczeń i funduszów emerytalnych
- PKD 65 - Ubezpieczenia, reasekuracja oraz fundusze emerytalne, z wyłączeniem obowiązkowego ubezpieczenia społecznego
- PKD 66 - Działalność wspomagająca usługi finansowe oraz ubezpieczenia i fundusze emerytalne
- PKD 68 - Działalność związana z obsługą rynku nieruchomości
- PKD 69 - Działalność prawnicza, rachunkowo-księgowa i doradztwo podatkowe
- PKD 70 - Działalność firm centralnych (head offices); doradztwo związane z zarządzaniem
- PKD 71 - Działalność w zakresie architektury i inżynierii; badania i analizy techniczne
- PKD 72 - Badania naukowe i prace rozwojowe
- PKD 73 - Reklama, badanie rynku i opinii publicznej
- PKD 74 - Pozostała działalność profesjonalna, naukowa i techniczna
- PKD 75 - Działalność weterinaryjna
- PKD 77 - Wynajem i dzierżawa
- PKD 78 - Działalność związana z zatrudnieniem
- PKD 79 - Działalność organizatorów turystyki, pośredników i agentów turystycznych oraz pozostała działalność usługowa w zakresie rezerwacji i działalności z nią związanej
- PKD 80 - Działalność detektywistyczna i ochroniarska
- PKD 81 - Działalność usługowa związana z utrzymaniem porządku w budynkach i zagospodarowaniem terenów zieleni
- PKD 82 - Działalność związana z administracyjną obsługą biura i pozostała działalność wspomagająca prowadzenie działalności gospodarczej
- PKD 84 - Administracja publiczna i obrona narodowa; obowiązkowe zabezpieczenia społeczne
- PKD 85 - Edukacja
- PKD 86 - Opieka zdrowotna
- PKD 87 - Pomoc społeczna z zakwaterowaniem
- PKD 88 - Pomoc społeczna bez zakwaterowania
- PKD 90 - Działalność twórcza związana z kulturą i rozrywką
- PKD 91 - Działalność bibliotek, archiwów, muzeów oraz pozostała działalność związana z kulturą
- PKD 92 - Działalność związana z grami losowymi i zakładami wzajemnymi
- PKD 93 - Działalność sportowa, rozrywkowa i rekreacyjna
- PKD 94 - Działalność organizacji członkowskich
- PKD 95 - Naprawa i konserwacja komputerów i artykułów użytku osobistego i domowego
- PKD 96 - Pozostała indywidualna działalność usługowa
- PKD 97 - Gospodarstwa domowe zatrudniające pracowników
- PKD 98 - Gospodarstwa domowe produkujące wyroby i świadczące usługi na własne potrzeby
- PKD 99 - Organizacje i zespoły eksterytorialne

---Przykłady---
{examples}

ZAPYTANIE UŻYTKOWNIKA: {query}

WYJŚCIE JSON (tylko polskie słowa kluczowe):"""

PROMPTS["keywords_extraction_examples"] = [
    """Przykład 1:

Zapytanie: "Klient posiada tartak i 2 maszyny, czy może je ubezpieczyć w produkcie SME"

Wyjście:
{
  "high_level_keywords": ["ubezpieczenie działalności", "SME", "produkcja drewno"],
  "low_level_keywords": ["tartak", "PKD 16", "maszyny", "polisa SME", "możliwość ubezpieczenia"]
}

""",
    """Przykład 2:

Zapytanie: "Jakie są wykluczenia w OC dla warsztatów samochodowych?"

Wyjście:
{
  "high_level_keywords": ["OC", "wykluczenia", "warsztat samochodowy", "naprawy pojazdów"],
  "low_level_keywords": ["PKD 45", "warsztat", "polisa OC", "wykluczenia OC", "wyjątki polisy"]
}

""",
    """Przykład 3:

Zapytanie: "Restauracja z 5 pracownikami, jakie ubezpieczenie?"

Wyjście:
{
  "high_level_keywords": ["gastronomia", "ubezpieczenie", "działalność usługowa"],
  "low_level_keywords": ["restauracja", "PKD 56", "pracownicy", "polisa gastronomia"]
}

""",
    """Przykład 4:

Zapytanie: "Sklep spożywczy, czy SME wyklucza sprzedaż alkoholu?"

Wyjście:
{
  "high_level_keywords": ["handel detaliczny", "SME", "wykluczenia"],
  "low_level_keywords": ["sklep spożywczy", "PKD 47", "alkohol", "wykluczenia SME", "wyjątki polisy"]
}

""",
]

# ============================================================================
# DEFAULT ENTITY TYPES IN POLISH
# ============================================================================
PROMPTS["default_entity_types_pl"] = [
    "osoba",
    "stworzenie",
    "organizacja",
    "lokalizacja",
    "wydarzenie",
    "koncepcja",
    "metoda",
    "treść",
    "dane",
    "artefakt",
    "obiekt_naturalny",
    "inny"
]


# ============================================================================
# CUSTOM PROMPTS LOADER - Load prompts from external JSON file
# ============================================================================
def _load_custom_prompts() -> None:
    """Load custom prompts from JSON file specified by LIGHTRAG_PROMPTS_FILE.

    This function allows overriding built-in prompts via an external JSON file,
    useful for ConfigMap-based configuration in Kubernetes/OKD deployments.

    Environment Variables:
        LIGHTRAG_PROMPTS_FILE: Path to JSON file containing custom prompts.
            If not set, built-in defaults are used.

    JSON Format:
        {
            "_meta": {"version": "1.0", "description": "optional metadata"},
            "prompt_key": "prompt value",
            ...
        }

    Notes:
        - Keys starting with '_' are treated as metadata and skipped
        - Unknown keys generate a warning and are skipped
        - Type mismatches generate a warning and are skipped
        - Partial overrides are supported (only specified keys are replaced)
    """
    import json
    import os
    from pathlib import Path

    from lightrag.utils import logger

    prompts_file = os.getenv("LIGHTRAG_PROMPTS_FILE")
    if not prompts_file:
        return

    prompts_path = Path(prompts_file)
    if not prompts_path.exists():
        logger.warning(f"Prompts file not found: {prompts_file}, using defaults")
        return

    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            custom_prompts = json.load(f)

        if not isinstance(custom_prompts, dict):
            logger.error(
                f"Invalid prompts file: expected dict, got {type(custom_prompts).__name__}"
            )
            return

        # Merge custom prompts (skip metadata keys starting with _)
        count = 0
        for key, value in custom_prompts.items():
            if key.startswith("_"):
                continue
            if key not in PROMPTS:
                logger.warning(f"Unknown prompt key: {key}")
                continue
            # Type validation
            if type(value) != type(PROMPTS[key]):
                logger.warning(
                    f"Type mismatch for '{key}': expected {type(PROMPTS[key]).__name__}, "
                    f"got {type(value).__name__}"
                )
                continue
            PROMPTS[key] = value
            count += 1

        logger.info(f"Loaded {count} custom prompts from {prompts_file}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse prompts file: {e}")
    except Exception as e:
        logger.error(f"Failed to load prompts file: {e}")


_load_custom_prompts()
