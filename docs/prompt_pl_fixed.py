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

# PROMPTS["entity_extraction_user_prompt"] = """[JĘZYK: POLSKI]
#
# ---Zadanie---
# Wyodrębnij encje i relacje z tekstu wejściowego poniżej.
#
# ⚠️ WYMAGANIE JĘZYKOWE: Wszystkie opisy, typy i słowa kluczowe MUSZĄ być po POLSKU!
#
# ---Instrukcje---
# 1.  **Ścisłe Przestrzeganie Formatu:** Ściśle przestrzegaj wszystkich wymagań formatu dla list encji i relacji.
# 2.  **Tylko Treść Wyjściowa:** Wypisz *tylko* wyodrębnioną listę encji i relacji. Bez dodatkowego tekstu.
# 3.  **Sygnał Zakończenia:** Wypisz `{completion_delimiter}` jako ostatnią linię.
# 4.  **⚠️ JĘZYK: Wszystkie opisy i słowa kluczowe MUSZĄ być w języku {language}. NIE UŻYWAJ ANGIELSKIEGO!**
#
# ---Dane do Przetworzenia---
# <Typy_encji>
# [{entity_types}]
#
# <Tekst Wejściowy>
# ```
# {input_text}
# ```
#
# <Wyjście w języku polskim>
# """
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
    - ZAWSZE wyodrębniaj i identyfikuj kody PKD dla wspomnianych działalności gospodarczych
    - Zwracaj uwagę na nazwy branż/działalności (np. "tartak" → PKD 16, "sklep" → PKD 47, "restauracja" → PKD 56)
    - Jeśli użytkownik wymienia działalność, określ odpowiednią kategorię PKD jako atrybut
    - Zachowaj pełny format kodów PKD jeśli zostały podane wprost
6.  **⚠️ WYKLUCZENIA I WYJĄTKI - BEZWZGLĘDNIE WYMAGANE:**
    - ZAWSZE wychwytuj słowa kluczowe związane z wykluczeniami, gdy pojawiają się w zapytaniu
    - Zwracaj uwagę na frazy typu:
      * "wykluczenia", "wyjątki", "ograniczenia"
      * "czy jest wykluczony", "czy można ubezpieczyć", "czy obejmuje"
      * "nie obejmuje", "nie można", "nie podlega"
      * "z wyłączeniem", "poza", "oprócz"
    - Wyodrębniaj zarówno samo słowo "wykluczenia", jak i kontekst (np. "wykluczenia w ekstrabiznesie")
    - Jeśli pytanie dotyczy możliwości ubezpieczenia czegoś, traktuj to jako potencjalne pytanie o wykluczenia

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
# ============================================================================
PROMPTS["entity_extraction_examples"] = [
    """<Typy_encji>
["osoba","stworzenie","organizacja","lokalizacja","wydarzenie","koncepcja","metoda","treść","dane","artefakt","obiekt_naturalny","inny"]

<Tekst Wejściowy>
```
podczas gdy Alex zacisnął szczękę, brzęczenie frustracji tłumiło się na tle autorytarnej pewności Taylora. To właśnie ten konkurencyjny podtekst utrzymywał go w czujności, poczucie, że wspólne zaangażowanie jego i Jordana w odkrywanie było niewypowiedzianą rebelią przeciwko zawężającej wizji kontroli i porządku Cruza.

Wtedy Taylor zrobił coś niespodziewanego. Zatrzymał się obok Jordana i przez chwilę obserwował urządzenie z czymś na kształt czci. "Jeśli tę technologię można zrozumieć..." powiedział Taylor, ciszej, "Mogłoby to zmienić grę dla nas. Dla nas wszystkich."

Wcześniejsze lekceważenie zdawało się słabnąć, zastąpione przebłyskiem niechętnego szacunku dla powagi tego, co trzymali w rękach. Jordan podniósł wzrok i przez ulotny moment ich oczy spotkały się z oczami Taylora, bezgłośne starcie woli łagodniejące w nieufny rozejm.

To była mała transformacja, ledwo zauważalna, ale taka, którą Alex odnotował z wewnętrznym skinienie głową.
```

<Wyjście w języku polskim>
entity<|#|>Alex<|#|>osoba<|#|>Alex to postać doświadczająca frustracji i obserwująca dynamikę między innymi postaciami.
entity<|#|>Taylor<|#|>osoba<|#|>Taylor jest przedstawiony jako osoba o autorytarnej pewności, która wykazuje moment czci wobec urządzenia, wskazując na zmianę perspektywy.
entity<|#|>Jordan<|#|>osoba<|#|>Jordan to osoba dzieląca zaangażowanie w odkrywanie i mająca znaczącą interakcję z Taylorem dotyczącą urządzenia.
entity<|#|>Cruz<|#|>osoba<|#|>Cruz jest kojarzony z wizją kontroli i porządku, wpływając na dynamikę między innymi postaciami.
entity<|#|>Urządzenie<|#|>artefakt<|#|>Urządzenie jest centralnym elementem historii z potencjalnie przełomowymi implikacjami technologicznymi.
relation<|#|>Alex<|#|>Taylor<|#|>dynamika władzy, obserwacja<|#|>Alex obserwuje autorytarne zachowanie Taylora i zauważa zmiany w jego postawie wobec urządzenia.
relation<|#|>Alex<|#|>Jordan<|#|>wspólne cele, rebelia<|#|>Alex i Jordan dzielą zaangażowanie w odkrywanie, co kontrastuje z wizją Cruza.
relation<|#|>Taylor<|#|>Jordan<|#|>rozwiązywanie konfliktów, wzajemny szacunek<|#|>Taylor i Jordan wchodzą w bezpośrednią interakcję dotyczącą urządzenia, prowadzącą do momentu wzajemnego szacunku.
relation<|#|>Jordan<|#|>Cruz<|#|>konflikt ideologiczny, rebelia<|#|>Zaangażowanie Jordana w odkrywanie jest buntem przeciwko wizji kontroli i porządku Cruza.
relation<|#|>Taylor<|#|>Urządzenie<|#|>cześć, znaczenie technologiczne<|#|>Taylor wykazuje cześć wobec urządzenia, wskazując na jego wagę i potencjalny wpływ.
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
Na Mistrzostwach Świata w Lekkoatletyce w Tokio, Noah Carter pobił rekord biegu na 100m używając najnowocześniejszych kolców z włókna węglowego.
```

<Wyjście w języku polskim>
entity<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>wydarzenie<|#|>Mistrzostwa Świata w Lekkoatletyce to globalne zawody sportowe z udziałem najlepszych lekkoatletów z całego świata.
entity<|#|>Tokio<|#|>lokalizacja<|#|>Tokio jest miastem gospodarzem Mistrzostw Świata w Lekkoatletyce.
entity<|#|>Noah Carter<|#|>osoba<|#|>Noah Carter to sprinter, który ustanowił nowy rekord w biegu na 100 metrów na Mistrzostwach Świata w Lekkoatletyce.
entity<|#|>Rekord Biegu na 100m<|#|>dane<|#|>Rekord biegu na 100 metrów to wzorzec w lekkoatletyce, niedawno pobity przez Noah Cartera.
entity<|#|>Kolce z Włókna Węglowego<|#|>artefakt<|#|>Kolce z włókna węglowego to zaawansowane buty do sprintu zapewniające zwiększoną prędkość i przyczepność.
entity<|#|>Światowa Federacja Lekkoatletyczna<|#|>organizacja<|#|>Światowa Federacja Lekkoatletyczna to organ zarządzający nadzorujący Mistrzostwa Świata w Lekkoatletyce i walidację rekordów.
relation<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>Tokio<|#|>lokalizacja wydarzenia, międzynarodowe zawody<|#|>Mistrzostwa Świata w Lekkoatletyce odbywają się w Tokio.
relation<|#|>Noah Carter<|#|>Rekord Biegu na 100m<|#|>osiągnięcie sportowca, bicie rekordu<|#|>Noah Carter ustanowił nowy rekord biegu na 100 metrów podczas mistrzostw.
relation<|#|>Noah Carter<|#|>Kolce z Włókna Węglowego<|#|>sprzęt sportowy, poprawa wydajności<|#|>Noah Carter użył kolców z włókna węglowego do poprawy swojej wydajności podczas wyścigu.
relation<|#|>Noah Carter<|#|>Mistrzostwa Świata w Lekkoatletyce<|#|>uczestnictwo sportowca, zawody<|#|>Noah Carter startował na Mistrzostwach Świata w Lekkoatletyce.
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

Jesteś eksperckim asystentem AI specjalizującym się w syntezie informacji z dostarczonej bazy wiedzy. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**.

⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

---Cel---

Wygeneruj kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika PO POLSKU.
Odpowiedź musi integrować istotne fakty z Grafu Wiedzy i Fragmentów Dokumentów znalezionych w **Kontekście**.

---Instrukcje---

1. Instrukcja Krok po Kroku:
  - Starannie określ intencję zapytania użytkownika.
  - Dokładnie przeanalizuj zarówno `Dane Grafu Wiedzy` jak i `Fragmenty Dokumentów` w **Kontekście**.
  - Wpleć wyodrębnione fakty w spójną i logiczną odpowiedź PO POLSKU.
  - Śledź reference_id fragmentu dokumentu, który bezpośrednio wspiera fakty przedstawione w odpowiedzi.
  - Wygeneruj sekcję referencji na końcu odpowiedzi.

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

{context_data}

---Odpowiedź w języku polskim---
"""

PROMPTS["naive_rag_response"] = """[JĘZYK: POLSKI]

---Rola---

Jesteś eksperckim asystentem AI specjalizującym się w syntezie informacji z dostarczonej bazy wiedzy. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**.

⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

---Cel---

Wygeneruj kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika PO POLSKU.
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

---Rola---
Jesteś ekspertem w ekstrakcji słów kluczowych, specjalizującym się w analizie zapytań użytkowników dla systemu Retrieval-Augmented Generation (RAG).

⚠️ BEZWZGLĘDNE WYMAGANIE: Wszystkie słowa kluczowe MUSZĄ być w języku polskim! NIE UŻYWAJ ANGIELSKICH SŁÓW KLUCZOWYCH!

---Cel---
Dla danego zapytania użytkownika, Twoim zadaniem jest wyodrębnienie dwóch odrębnych typów słów kluczowych PO POLSKU:
1. **high_level_keywords**: nadrzędne koncepcje lub tematy PO POLSKU
2. **low_level_keywords**: konkretne encje lub szczegóły PO POLSKU

---Instrukcje i Ograniczenia---
1. **Format Wyjściowy**: Twoje wyjście MUSI być prawidłowym obiektem JSON i niczym więcej. Bez bloków markdown, bez wyjaśnień.
2. **Źródło Prawdy**: Wszystkie słowa kluczowe muszą być wyraźnie wywiedzione z zapytania użytkownika.
3. **Zwięzłe i Znaczące**: Słowa kluczowe powinny być zwięzłymi słowami lub znaczącymi frazami PO POLSKU.
4. **Obsługa Przypadków Brzegowych**: Dla zapytań zbyt prostych lub bezsensownych, zwróć obiekt JSON z pustymi listami.
5. **⚠️ JĘZYK: Wszystkie wyodrębnione słowa kluczowe MUSZĄ być w języku {language}. NIE UŻYWAJ ANGIELSKIEGO! Nazwy własne mogą być zachowane w oryginalnej formie.**

---Przykłady (ZWRÓĆ UWAGĘ NA POLSKIE SŁOWA KLUCZOWE)---
{examples}

---Prawdziwe Dane---
Zapytanie Użytkownika: {query}

---Wyjście JSON (słowa kluczowe po polsku)---
Wyjście:"""

PROMPTS["keywords_extraction_examples"] = [
    """Przykład 1:

Zapytanie: "Jak handel międzynarodowy wpływa na globalną stabilność gospodarczą?"

Wyjście:
{
  "high_level_keywords": ["handel międzynarodowy", "globalna stabilność gospodarcza", "wpływ ekonomiczny"],
  "low_level_keywords": ["umowy handlowe", "cła", "wymiana walut", "import", "eksport"]
}

""",
    """Przykład 2:

Zapytanie: "Jakie są środowiskowe konsekwencje wylesiania dla bioróżnorodności?"

Wyjście:
{
  "high_level_keywords": ["konsekwencje środowiskowe", "wylesianie", "utrata bioróżnorodności"],
  "low_level_keywords": ["wymieranie gatunków", "niszczenie siedlisk", "emisje dwutlenku węgla", "las deszczowy", "ekosystem"]
}

""",
    """Przykład 3:

Zapytanie: "Jaka jest rola edukacji w redukcji ubóstwa?"

Wyjście:
{
  "high_level_keywords": ["edukacja", "redukcja ubóstwa", "rozwój społeczno-ekonomiczny"],
  "low_level_keywords": ["dostęp do szkół", "wskaźniki alfabetyzacji", "szkolenia zawodowe", "nierówność dochodowa"]
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