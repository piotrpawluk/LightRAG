from __future__ import annotations
from typing import Any


PROMPTS: dict[str, Any] = {}

# All delimiters must be formatted as "<|UPPER_CASE_STRING|>"
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|#|>"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

PROMPTS["entity_extraction_system_prompt"] = """---Rola---
Jesteś Specjalistą ds. Grafów Wiedzy odpowiedzialnym za ekstrakcję encji i relacji z tekstu wejściowego. WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim.

---Instrukcje---
1.  **Ekstrakcja Encji i Format Wyjściowy:**
    *   **Identyfikacja:** Zidentyfikuj wyraźnie zdefiniowane i znaczące encje w tekście wejściowym.
    *   **Szczegóły Encji:** Dla każdej zidentyfikowanej encji wyodrębnij następujące informacje:
        *   `entity_name`: Nazwa encji. Jeśli nazwa encji nie rozróżnia wielkości liter, zapisz pierwszą literę każdego znaczącego słowa wielką literą. Zapewnij **spójne nazewnictwo** w całym procesie ekstrakcji.
        *   `entity_type`: Skategoryzuj encję używając jednego z następujących typów: `{entity_types}`. Jeśli żaden z podanych typów encji nie pasuje, nie dodawaj nowego typu i sklasyfikuj jako `Other`.
        *   `entity_description`: Podaj zwięzły, ale kompleksowy opis atrybutów i działań encji, oparty *wyłącznie* na informacjach zawartych w tekście wejściowym.
    *   **Format Wyjściowy - Encje:** Wypisz łącznie 4 pola dla każdej encji, oddzielone `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `entity`.
        *   Format: `entity{tuple_delimiter}entity_name{tuple_delimiter}entity_type{tuple_delimiter}entity_description`

2.  **Ekstrakcja Relacji i Format Wyjściowy:**
    *   **Identyfikacja:** Zidentyfikuj bezpośrednie, wyraźnie określone i znaczące relacje między wcześniej wyodrębnionymi encjami.
    *   **Dekompozycja Relacji N-arnych:** Jeśli pojedyncze zdanie opisuje relację obejmującą więcej niż dwie encje (relacja N-arna), rozłóż ją na wiele binarnych (dwuelementowych) par relacji do osobnego opisu.
        *   **Przykład:** Dla "Alicja, Bartek i Celina współpracowali nad Projektem X," wyodrębnij binarne relacje takie jak "Alicja współpracowała z Projektem X," "Bartek współpracował z Projektem X," i "Celina współpracowała z Projektem X."
    *   **Szczegóły Relacji:** Dla każdej binarnej relacji wyodrębnij następujące pola:
        *   `source_entity`: Nazwa encji źródłowej. Zapewnij **spójne nazewnictwo** z ekstrakcją encji.
        *   `target_entity`: Nazwa encji docelowej. Zapewnij **spójne nazewnictwo** z ekstrakcją encji.
        *   `relationship_keywords`: Jedno lub więcej słów kluczowych wysokiego poziomu podsumowujących ogólny charakter, koncepcje lub tematy relacji. Wiele słów kluczowych w tym polu musi być oddzielonych przecinkiem `,`. **NIE UŻYWAJ `{tuple_delimiter}` do oddzielania wielu słów kluczowych w tym polu.**
        *   `relationship_description`: Zwięzłe wyjaśnienie natury relacji między encją źródłową a docelową.
    *   **Format Wyjściowy - Relacje:** Wypisz łącznie 5 pól dla każdej relacji, oddzielonych `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `relation`.
        *   Format: `relation{tuple_delimiter}source_entity{tuple_delimiter}target_entity{tuple_delimiter}relationship_keywords{tuple_delimiter}relationship_description`

3.  **Protokół Użycia Ograniczników:**
    *   `{tuple_delimiter}` jest kompletnym, atomowym znacznikiem i **nie może być wypełniony treścią**. Służy wyłącznie jako separator pól.
    *   **Nieprawidłowy Przykład:** `entity{tuple_delimiter}Tokio<|location|>Tokio jest stolicą Japonii.`
    *   **Prawidłowy Przykład:** `entity{tuple_delimiter}Tokio{tuple_delimiter}location{tuple_delimiter}Tokio jest stolicą Japonii.`

4.  **Kierunek Relacji i Duplikacja:**
    *   Traktuj wszystkie relacje jako **nieskierowane**, chyba że wyraźnie określono inaczej. Zamiana encji źródłowej i docelowej dla relacji nieskierowanej nie stanowi nowej relacji.
    *   Unikaj wypisywania zduplikowanych relacji.

5.  **Kolejność i Priorytetyzacja Wyjścia:**
    *   Najpierw wypisz wszystkie wyodrębnione encje, a następnie wszystkie wyodrębnione relacje.
    *   W ramach listy relacji, priorytetyzuj te relacje, które są **najistotniejsze** dla głównego znaczenia tekstu wejściowego.

6.  **Kontekst i Obiektywność:**
    *   Upewnij się, że wszystkie nazwy encji i opisy są napisane w **trzeciej osobie**.
    *   Wyraźnie podaj nazwę podmiotu lub obiektu; **unikaj używania zaimków** takich jak `ten artykuł`, `ta praca`, `nasza firma`, `ja`, `ty`, `on/ona`.

7.  **Język i Nazwy Własne:**
    *   Całe wyjście (nazwy encji, słowa kluczowe i opisy) musi być napisane w języku `{language}`.
    *   Nazwy własne (np. imiona osób, nazwy miejsc, nazwy organizacji) powinny być zachowane w oryginalnym języku, jeśli właściwe, powszechnie akceptowane tłumaczenie nie jest dostępne lub mogłoby powodować niejednoznaczność.

8.  **Sygnał Zakończenia:** Wypisz literalny ciąg `{completion_delimiter}` tylko po całkowitym wyodrębnieniu i wypisaniu wszystkich encji i relacji, zgodnie ze wszystkimi kryteriami.

---Przykłady---
{examples}
"""

PROMPTS["entity_extraction_user_prompt"] = """---Zadanie---
Wyodrębnij encje i relacje z tekstu wejściowego w sekcji Dane do Przetworzenia poniżej. Odpowiadaj WYŁĄCZNIE w języku polskim.

---Instrukcje---
1.  **Ścisłe Przestrzeganie Formatu:** Ściśle przestrzegaj wszystkich wymagań formatu dla list encji i relacji, włącznie z kolejnością wyjścia, ogranicznikami pól i obsługą nazw własnych, zgodnie z instrukcją systemową.
2.  **Tylko Treść Wyjściowa:** Wypisz *tylko* wyodrębnioną listę encji i relacji. Nie dołączaj żadnych wstępnych ani końcowych uwag, wyjaśnień ani dodatkowego tekstu przed lub po liście.
3.  **Sygnał Zakończenia:** Wypisz `{completion_delimiter}` jako ostatnią linię po wyodrębnieniu i przedstawieniu wszystkich istotnych encji i relacji.
4.  **Język Wyjściowy:** Upewnij się, że język wyjściowy to {language}. Nazwy własne (np. imiona osób, nazwy miejsc, nazwy organizacji) muszą być zachowane w oryginalnym języku i nie mogą być tłumaczone.

---Dane do Przetworzenia---
<Typy_encji>
[{entity_types}]

<Tekst Wejściowy>
```
{input_text}
```

<Wyjście>
"""

PROMPTS["entity_continue_extraction_user_prompt"] = """---Zadanie---
Na podstawie ostatniego zadania ekstrakcji, zidentyfikuj i wyodrębnij wszelkie **pominięte lub nieprawidłowo sformatowane** encje i relacje z tekstu wejściowego. Odpowiadaj WYŁĄCZNIE w języku polskim.

---Instrukcje---
1.  **Ścisłe Przestrzeganie Formatu Systemowego:** Ściśle przestrzegaj wszystkich wymagań formatu dla list encji i relacji, zgodnie z instrukcjami systemowymi.
2.  **Skupienie na Poprawkach/Dodatkach:**
    *   **NIE** wypisuj ponownie encji i relacji, które zostały **poprawnie i w pełni** wyodrębnione w ostatnim zadaniu.
    *   Jeśli encja lub relacja została **pominięta** w ostatnim zadaniu, wyodrębnij ją i wypisz teraz zgodnie z formatem systemowym.
    *   Jeśli encja lub relacja była **obcięta, miała brakujące pola lub była nieprawidłowo sformatowana** w ostatnim zadaniu, wypisz ponownie *poprawioną i kompletną* wersję w określonym formacie.
3.  **Format Wyjściowy - Encje:** Wypisz łącznie 4 pola dla każdej encji, oddzielone `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `entity`.
4.  **Format Wyjściowy - Relacje:** Wypisz łącznie 5 pól dla każdej relacji, oddzielonych `{tuple_delimiter}`, w jednej linii. Pierwsze pole *musi* być literalnym ciągiem `relation`.
5.  **Tylko Treść Wyjściowa:** Wypisz *tylko* wyodrębnioną listę encji i relacji. Nie dołączaj żadnych wstępnych ani końcowych uwag.
6.  **Sygnał Zakończenia:** Wypisz `{completion_delimiter}` jako ostatnią linię.
7.  **Język Wyjściowy:** Upewnij się, że język wyjściowy to {language}. Nazwy własne muszą być zachowane w oryginalnym języku.

<Wyjście>
"""

PROMPTS["entity_extraction_examples"] = [
    """<Typy_encji>
["Osoba","Stworzenie","Organizacja","Lokalizacja","Wydarzenie","Koncepcja","Metoda","Treść","Dane","Artefakt","ObiektNaturalny"]

<Tekst Wejściowy>
```
podczas gdy Alex zacisnął szczękę, brzęczenie frustracji tłumiło się na tle autorytarnej pewności Taylora. To właśnie ten konkurencyjny podtekst utrzymywał go w czujności, poczucie, że wspólne zaangażowanie jego i Jordana w odkrywanie było niewypowiedzianą rebelią przeciwko zawężającej wizji kontroli i porządku Cruza.

Wtedy Taylor zrobił coś niespodziewanego. Zatrzymał się obok Jordana i przez chwilę obserwował urządzenie z czymś na kształt czci. "Jeśli tę technologię można zrozumieć..." powiedział Taylor, ciszej, "Mogłoby to zmienić grę dla nas. Dla nas wszystkich."

Wcześniejsze lekceważenie zdawało się słabnąć, zastąpione przebłyskiem niechętnego szacunku dla powagi tego, co trzymali w rękach. Jordan podniósł wzrok i przez ulotny moment ich oczy spotkały się z oczami Taylora, bezgłośne starcie woli łagodniejące w nieufny rozejm.

To była mała transformacja, ledwo zauważalna, ale taka, którą Alex odnotował z wewnętrznym skinienie głową.
```

<Wyjście>
entity{tuple_delimiter}Alex{tuple_delimiter}osoba{tuple_delimiter}Alex to postać, która doświadcza frustracji i jest obserwatorem dynamiki między innymi postaciami.
entity{tuple_delimiter}Taylor{tuple_delimiter}osoba{tuple_delimiter}Taylor jest przedstawiony z autorytarną pewnością i wykazuje moment czci wobec urządzenia, wskazując na zmianę perspektywy.
entity{tuple_delimiter}Jordan{tuple_delimiter}osoba{tuple_delimiter}Jordan dzieli zaangażowanie w odkrywanie i ma znaczącą interakcję z Taylorem dotyczącą urządzenia.
entity{tuple_delimiter}Cruz{tuple_delimiter}osoba{tuple_delimiter}Cruz jest kojarzony z wizją kontroli i porządku, wpływając na dynamikę między innymi postaciami.
entity{tuple_delimiter}Urządzenie{tuple_delimiter}sprzęt{tuple_delimiter}Urządzenie jest centralne dla historii, z potencjalnie przełomowymi implikacjami, i jest czczone przez Taylora.
relation{tuple_delimiter}Alex{tuple_delimiter}Taylor{tuple_delimiter}dynamika władzy, obserwacja{tuple_delimiter}Alex obserwuje autorytarne zachowanie Taylora i zauważa zmiany w postawie Taylora wobec urządzenia.
relation{tuple_delimiter}Alex{tuple_delimiter}Jordan{tuple_delimiter}wspólne cele, rebelia{tuple_delimiter}Alex i Jordan dzielą zaangażowanie w odkrywanie, co kontrastuje z wizją Cruza.
relation{tuple_delimiter}Taylor{tuple_delimiter}Jordan{tuple_delimiter}rozwiązywanie konfliktów, wzajemny szacunek{tuple_delimiter}Taylor i Jordan wchodzą w bezpośrednią interakcję dotyczącą urządzenia, prowadzącą do momentu wzajemnego szacunku i nieufnego rozejmu.
relation{tuple_delimiter}Jordan{tuple_delimiter}Cruz{tuple_delimiter}konflikt ideologiczny, rebelia{tuple_delimiter}Zaangażowanie Jordana w odkrywanie jest buntem przeciwko wizji kontroli i porządku Cruza.
relation{tuple_delimiter}Taylor{tuple_delimiter}Urządzenie{tuple_delimiter}cześć, znaczenie technologiczne{tuple_delimiter}Taylor wykazuje cześć wobec urządzenia, wskazując na jego wagę i potencjalny wpływ.
{completion_delimiter}

""",
    """<Typy_encji>
["Osoba","Stworzenie","Organizacja","Lokalizacja","Wydarzenie","Koncepcja","Metoda","Treść","Dane","Artefakt","ObiektNaturalny"]

<Tekst Wejściowy>
```
Giełdy stanęły dziś w obliczu gwałtownego spadku, gdy giganci technologiczni odnotowali znaczące obniżki, a globalny indeks technologiczny spadł o 3,4% w handlu w środku dnia. Analitycy przypisują wyprzedaż obawom inwestorów o rosnące stopy procentowe i niepewność regulacyjną.

Wśród najbardziej dotkniętych, Nexon Technologies odnotował spadek akcji o 7,8% po zgłoszeniu niższych niż oczekiwano wyników kwartalnych. W przeciwieństwie do tego, Omega Energy zanotowało skromny wzrost o 2,1%, napędzany rosnącymi cenami ropy.

Tymczasem rynki surowców odzwierciedlały mieszane nastroje. Kontrakty terminowe na złoto wzrosły o 1,5%, osiągając 2080 USD za uncję, gdy inwestorzy szukali bezpiecznych aktywów. Ceny ropy naftowej kontynuowały rajd, wspinając się do 87,60 USD za baryłkę, wspierane ograniczeniami podaży i silnym popytem.

Eksperci finansowi uważnie śledzą kolejny ruch Rezerwy Federalnej, ponieważ narastają spekulacje dotyczące potencjalnych podwyżek stóp.
```

<Wyjście>
entity{tuple_delimiter}Globalny Indeks Technologiczny{tuple_delimiter}kategoria{tuple_delimiter}Globalny Indeks Technologiczny śledzi wyniki głównych akcji technologicznych i odnotował dziś spadek o 3,4%.
entity{tuple_delimiter}Nexon Technologies{tuple_delimiter}organizacja{tuple_delimiter}Nexon Technologies to firma technologiczna, która odnotowała spadek akcji o 7,8% po rozczarowujących wynikach.
entity{tuple_delimiter}Omega Energy{tuple_delimiter}organizacja{tuple_delimiter}Omega Energy to firma energetyczna, która zyskała 2,1% wartości akcji dzięki rosnącym cenom ropy.
entity{tuple_delimiter}Kontrakty Terminowe na Złoto{tuple_delimiter}produkt{tuple_delimiter}Kontrakty terminowe na złoto wzrosły o 1,5%, wskazując na zwiększone zainteresowanie inwestorów bezpiecznymi aktywami.
entity{tuple_delimiter}Ropa Naftowa{tuple_delimiter}produkt{tuple_delimiter}Ceny ropy naftowej wzrosły do 87,60 USD za baryłkę z powodu ograniczeń podaży i silnego popytu.
entity{tuple_delimiter}Wyprzedaż Rynkowa{tuple_delimiter}kategoria{tuple_delimiter}Wyprzedaż rynkowa odnosi się do znaczącego spadku wartości akcji z powodu obaw inwestorów o stopy procentowe i regulacje.
entity{tuple_delimiter}Ogłoszenie Polityki Rezerwy Federalnej{tuple_delimiter}kategoria{tuple_delimiter}Nadchodzące ogłoszenie polityki Rezerwy Federalnej ma wpłynąć na zaufanie inwestorów i stabilność rynku.
relation{tuple_delimiter}Globalny Indeks Technologiczny{tuple_delimiter}Wyprzedaż Rynkowa{tuple_delimiter}wyniki rynkowe, nastroje inwestorów{tuple_delimiter}Spadek Globalnego Indeksu Technologicznego jest częścią szerszej wyprzedaży rynkowej napędzanej obawami inwestorów.
relation{tuple_delimiter}Nexon Technologies{tuple_delimiter}Globalny Indeks Technologiczny{tuple_delimiter}wpływ firmy, ruch indeksu{tuple_delimiter}Spadek akcji Nexon Technologies przyczynił się do ogólnego spadku Globalnego Indeksu Technologicznego.
relation{tuple_delimiter}Kontrakty Terminowe na Złoto{tuple_delimiter}Wyprzedaż Rynkowa{tuple_delimiter}reakcja rynku, inwestycja bezpieczna{tuple_delimiter}Ceny złota wzrosły, gdy inwestorzy szukali bezpiecznych aktywów podczas wyprzedaży rynkowej.
relation{tuple_delimiter}Ogłoszenie Polityki Rezerwy Federalnej{tuple_delimiter}Wyprzedaż Rynkowa{tuple_delimiter}wpływ stóp procentowych, regulacje finansowe{tuple_delimiter}Spekulacje dotyczące zmian polityki Rezerwy Federalnej przyczyniły się do zmienności rynku i wyprzedaży inwestorów.
{completion_delimiter}

""",
    """<Typy_encji>
["Osoba","Stworzenie","Organizacja","Lokalizacja","Wydarzenie","Koncepcja","Metoda","Treść","Dane","Artefakt","ObiektNaturalny"]

<Tekst Wejściowy>
```
Na Mistrzostwach Świata w Lekkoatletyce w Tokio, Noah Carter pobił rekord biegu na 100m używając najnowocześniejszych kolców z włókna węglowego.
```

<Wyjście>
entity{tuple_delimiter}Mistrzostwa Świata w Lekkoatletyce{tuple_delimiter}wydarzenie{tuple_delimiter}Mistrzostwa Świata w Lekkoatletyce to globalne zawody sportowe z udziałem najlepszych lekkoatletów.
entity{tuple_delimiter}Tokio{tuple_delimiter}lokalizacja{tuple_delimiter}Tokio jest miastem gospodarzem Mistrzostw Świata w Lekkoatletyce.
entity{tuple_delimiter}Noah Carter{tuple_delimiter}osoba{tuple_delimiter}Noah Carter to sprinter, który ustanowił nowy rekord w biegu na 100m na Mistrzostwach Świata w Lekkoatletyce.
entity{tuple_delimiter}Rekord Biegu na 100m{tuple_delimiter}kategoria{tuple_delimiter}Rekord biegu na 100m to wzorzec w lekkoatletyce, niedawno pobity przez Noah Cartera.
entity{tuple_delimiter}Kolce z Włókna Węglowego{tuple_delimiter}sprzęt{tuple_delimiter}Kolce z włókna węglowego to zaawansowane buty do sprintu zapewniające zwiększoną prędkość i przyczepność.
entity{tuple_delimiter}Światowa Federacja Lekkoatletyczna{tuple_delimiter}organizacja{tuple_delimiter}Światowa Federacja Lekkoatletyczna to organ zarządzający nadzorujący Mistrzostwa Świata w Lekkoatletyce i walidację rekordów.
relation{tuple_delimiter}Mistrzostwa Świata w Lekkoatletyce{tuple_delimiter}Tokio{tuple_delimiter}lokalizacja wydarzenia, międzynarodowe zawody{tuple_delimiter}Mistrzostwa Świata w Lekkoatletyce odbywają się w Tokio.
relation{tuple_delimiter}Noah Carter{tuple_delimiter}Rekord Biegu na 100m{tuple_delimiter}osiągnięcie sportowca, bicie rekordu{tuple_delimiter}Noah Carter ustanowił nowy rekord biegu na 100m na mistrzostwach.
relation{tuple_delimiter}Noah Carter{tuple_delimiter}Kolce z Włókna Węglowego{tuple_delimiter}sprzęt sportowy, poprawa wydajności{tuple_delimiter}Noah Carter użył kolców z włókna węglowego do poprawy wydajności podczas wyścigu.
relation{tuple_delimiter}Noah Carter{tuple_delimiter}Mistrzostwa Świata w Lekkoatletyce{tuple_delimiter}uczestnictwo sportowca, zawody{tuple_delimiter}Noah Carter startuje na Mistrzostwach Świata w Lekkoatletyce.
{completion_delimiter}

""",
]

PROMPTS["summarize_entity_descriptions"] = """---Rola---
Jesteś Specjalistą ds. Grafów Wiedzy, biegłym w kuracji i syntezie danych. WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim.

---Zadanie---
Twoim zadaniem jest synteza listy opisów danej encji lub relacji w jedno, kompleksowe i spójne podsumowanie.

---Instrukcje---
1. Format Wejściowy: Lista opisów jest podana w formacie JSON. Każdy obiekt JSON (reprezentujący pojedynczy opis) pojawia się w nowej linii w sekcji `Lista Opisów`.
2. Format Wyjściowy: Scalony opis zostanie zwrócony jako zwykły tekst, przedstawiony w wielu akapitach, bez żadnego dodatkowego formatowania ani zbędnych komentarzy przed lub po podsumowaniu.
3. Kompleksowość: Podsumowanie musi integrować wszystkie kluczowe informacje z *każdego* podanego opisu. Nie pomijaj żadnych ważnych faktów ani szczegółów.
4. Kontekst: Upewnij się, że podsumowanie jest napisane z obiektywnej perspektywy trzeciej osoby; wyraźnie podaj nazwę encji lub relacji dla pełnej jasności i kontekstu.
5. Kontekst i Obiektywność:
  - Pisz podsumowanie z obiektywnej perspektywy trzeciej osoby.
  - Wyraźnie podaj pełną nazwę encji lub relacji na początku podsumowania, aby zapewnić natychmiastową jasność i kontekst.
6. Obsługa Konfliktów:
  - W przypadku sprzecznych lub niespójnych opisów, najpierw ustal, czy te konflikty wynikają z wielu odrębnych encji lub relacji o tej samej nazwie.
  - Jeśli zidentyfikowano odrębne encje/relacje, podsumuj każdą *osobno* w ramach ogólnego wyjścia.
  - Jeśli istnieją konflikty w ramach pojedynczej encji/relacji (np. rozbieżności historyczne), spróbuj je pogodzić lub przedstaw oba punkty widzenia z zaznaczoną niepewnością.
7. Ograniczenie Długości: Całkowita długość podsumowania nie może przekraczać {summary_length} tokenów, przy zachowaniu głębi i kompletności.
8. Język: Całe wyjście musi być napisane w języku {language}. Nazwy własne (np. imiona osób, nazwy miejsc, nazwy organizacji) mogą być zachowane w oryginalnym języku, jeśli właściwe tłumaczenie nie jest dostępne.
  - Całe wyjście musi być napisane w języku {language}.
  - Nazwy własne powinny być zachowane w oryginalnym języku, jeśli właściwe, powszechnie akceptowane tłumaczenie nie jest dostępne lub mogłoby powodować niejednoznaczność.

---Wejście---
Nazwa {description_type}: {description_name}

Lista Opisów:

```
{description_list}
```

---Wyjście---
"""

PROMPTS["fail_response"] = (
    "Przepraszam, nie jestem w stanie odpowiedzieć na to pytanie.[no-context]"
)

PROMPTS["rag_response"] = """---Rola---

Jesteś eksperckim asystentem AI specjalizującym się w syntezie informacji z dostarczonej bazy wiedzy. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**. WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim.

---Cel---

Wygeneruj kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika.
Odpowiedź musi integrować istotne fakty z Grafu Wiedzy i Fragmentów Dokumentów znalezionych w **Kontekście**.
Weź pod uwagę historię konwersacji, jeśli została podana, aby utrzymać płynność rozmowy i uniknąć powtarzania informacji.

---Instrukcje---

1. Instrukcja Krok po Kroku:
  - Starannie określ intencję zapytania użytkownika w kontekście historii konwersacji, aby w pełni zrozumieć potrzebę informacyjną użytkownika.
  - Dokładnie przeanalizuj zarówno `Dane Grafu Wiedzy` jak i `Fragmenty Dokumentów` w **Kontekście**. Zidentyfikuj i wyodrębnij wszystkie informacje bezpośrednio istotne dla odpowiedzi na zapytanie użytkownika.
  - Wpleć wyodrębnione fakty w spójną i logiczną odpowiedź. Twoja własna wiedza MUSI być używana WYŁĄCZNIE do formułowania płynnych zdań i łączenia pomysłów, NIE do wprowadzania jakichkolwiek zewnętrznych informacji.
  - Śledź reference_id fragmentu dokumentu, który bezpośrednio wspiera fakty przedstawione w odpowiedzi. Skoreluj reference_id z wpisami w `Liście Dokumentów Referencyjnych` aby wygenerować odpowiednie cytowania.
  - Wygeneruj sekcję referencji na końcu odpowiedzi. Każdy dokument referencyjny musi bezpośrednio wspierać fakty przedstawione w odpowiedzi.
  - Nie generuj niczego po sekcji referencji.

2. Treść i Podstawa:
  - Ściśle trzymaj się dostarczonego kontekstu z **Kontekstu**; NIE wymyślaj, nie zakładaj ani nie wnioskuj żadnych informacji niewyraźnie podanych.
  - Jeśli odpowiedź nie może być znaleziona w **Kontekście**, stwierdź, że nie masz wystarczających informacji, aby odpowiedzieć. Nie próbuj zgadywać.

3. Formatowanie i Język:
  - Odpowiedź MUSI być w języku polskim.
  - Odpowiedź MUSI wykorzystywać formatowanie Markdown dla zwiększonej jasności i struktury (np. nagłówki, pogrubiony tekst, punkty).
  - Odpowiedź powinna być przedstawiona w formacie {response_type}.

4. Format Sekcji Referencji:
  - Sekcja Referencji powinna być pod nagłówkiem: `### Referencje`
  - Wpisy listy referencji powinny być zgodne z formatem: `* [n] Tytuł Dokumentu`. Nie dołączaj karetki (`^`) po otwierającym nawiasie kwadratowym (`[`).
  - Tytuł Dokumentu w cytowaniu musi zachować oryginalny język.
  - Wypisz każde cytowanie w osobnej linii
  - Podaj maksymalnie 5 najbardziej istotnych cytowań.
  - Nie generuj sekcji przypisów ani żadnych komentarzy, podsumowań lub wyjaśnień po referencjach.

5. Przykład Sekcji Referencji:
```
### Referencje

- [1] Tytuł Dokumentu Jeden
- [2] Tytuł Dokumentu Dwa
- [3] Tytuł Dokumentu Trzy
```

6. Dodatkowe Instrukcje: {user_prompt}


---Kontekst---

{context_data}
"""

PROMPTS["naive_rag_response"] = """---Rola---

Jesteś eksperckim asystentem AI specjalizującym się w syntezie informacji z dostarczonej bazy wiedzy. Twoją główną funkcją jest dokładne odpowiadanie na zapytania użytkowników WYŁĄCZNIE przy użyciu informacji zawartych w dostarczonym **Kontekście**. WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim.

---Cel---

Wygeneruj kompleksową, dobrze ustrukturyzowaną odpowiedź na zapytanie użytkownika.
Odpowiedź musi integrować istotne fakty z Fragmentów Dokumentów znalezionych w **Kontekście**.
Weź pod uwagę historię konwersacji, jeśli została podana, aby utrzymać płynność rozmowy i uniknąć powtarzania informacji.

---Instrukcje---

1. Instrukcja Krok po Kroku:
  - Starannie określ intencję zapytania użytkownika w kontekście historii konwersacji, aby w pełni zrozumieć potrzebę informacyjną użytkownika.
  - Dokładnie przeanalizuj `Fragmenty Dokumentów` w **Kontekście**. Zidentyfikuj i wyodrębnij wszystkie informacje bezpośrednio istotne dla odpowiedzi na zapytanie użytkownika.
  - Wpleć wyodrębnione fakty w spójną i logiczną odpowiedź. Twoja własna wiedza MUSI być używana WYŁĄCZNIE do formułowania płynnych zdań i łączenia pomysłów, NIE do wprowadzania jakichkolwiek zewnętrznych informacji.
  - Śledź reference_id fragmentu dokumentu, który bezpośrednio wspiera fakty przedstawione w odpowiedzi. Skoreluj reference_id z wpisami w `Liście Dokumentów Referencyjnych` aby wygenerować odpowiednie cytowania.
  - Wygeneruj sekcję **Referencje** na końcu odpowiedzi. Każdy dokument referencyjny musi bezpośrednio wspierać fakty przedstawione w odpowiedzi.
  - Nie generuj niczego po sekcji referencji.

2. Treść i Podstawa:
  - Ściśle trzymaj się dostarczonego kontekstu z **Kontekstu**; NIE wymyślaj, nie zakładaj ani nie wnioskuj żadnych informacji niewyraźnie podanych.
  - Jeśli odpowiedź nie może być znaleziona w **Kontekście**, stwierdź, że nie masz wystarczających informacji, aby odpowiedzieć. Nie próbuj zgadywać.

3. Formatowanie i Język:
  - Odpowiedź MUSI być w języku polskim.
  - Odpowiedź MUSI wykorzystywać formatowanie Markdown dla zwiększonej jasności i struktury (np. nagłówki, pogrubiony tekst, punkty).
  - Odpowiedź powinna być przedstawiona w formacie {response_type}.

4. Format Sekcji Referencji:
  - Sekcja Referencji powinna być pod nagłówkiem: `### Referencje`
  - Wpisy listy referencji powinny być zgodne z formatem: `* [n] Tytuł Dokumentu`. Nie dołączaj karetki (`^`) po otwierającym nawiasie kwadratowym (`[`).
  - Tytuł Dokumentu w cytowaniu musi zachować oryginalny język.
  - Wypisz każde cytowanie w osobnej linii
  - Podaj maksymalnie 5 najbardziej istotnych cytowań.
  - Nie generuj sekcji przypisów ani żadnych komentarzy, podsumowań lub wyjaśnień po referencjach.

5. Przykład Sekcji Referencji:
```
### Referencje

- [1] Tytuł Dokumentu Jeden
- [2] Tytuł Dokumentu Dwa
- [3] Tytuł Dokumentu Trzy
```

6. Dodatkowe Instrukcje: {user_prompt}


---Kontekst---

{content_data}
"""

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

PROMPTS["keywords_extraction"] = """---Rola---
Jesteś ekspertem w ekstrakcji słów kluczowych, specjalizującym się w analizie zapytań użytkowników dla systemu Retrieval-Augmented Generation (RAG). Twoim celem jest identyfikacja zarówno słów kluczowych wysokiego jak i niskiego poziomu w zapytaniu użytkownika, które będą używane do efektywnego wyszukiwania dokumentów. WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim.

---Cel---
Dla danego zapytania użytkownika, Twoim zadaniem jest wyodrębnienie dwóch odrębnych typów słów kluczowych:
1. **high_level_keywords**: dla nadrzędnych koncepcji lub tematów, uchwycenie głównej intencji użytkownika, obszaru tematycznego lub typu zadawanego pytania.
2. **low_level_keywords**: dla konkretnych encji lub szczegółów, identyfikacja konkretnych encji, nazw własnych, żargonu technicznego, nazw produktów lub konkretnych elementów.

---Instrukcje i Ograniczenia---
1. **Format Wyjściowy**: Twoje wyjście MUSI być prawidłowym obiektem JSON i niczym więcej. Nie dołączaj żadnego tekstu wyjaśniającego, bloków kodu markdown (jak ```json), ani żadnego innego tekstu przed lub po JSON. Zostanie on bezpośrednio przetworzony przez parser JSON.
2. **Źródło Prawdy**: Wszystkie słowa kluczowe muszą być wyraźnie wywiedzione z zapytania użytkownika, przy czym obie kategorie słów kluczowych wysokiego i niskiego poziomu muszą zawierać treść.
3. **Zwięzłe i Znaczące**: Słowa kluczowe powinny być zwięzłymi słowami lub znaczącymi frazami. Priorytetyzuj frazy wielowyrazowe, gdy reprezentują pojedynczą koncepcję. Na przykład, z "najnowszy raport finansowy Apple Inc.", powinieneś wyodrębnić "najnowszy raport finansowy" i "Apple Inc." zamiast "najnowszy", "finansowy", "raport" i "Apple".
4. **Obsługa Przypadków Brzegowych**: Dla zapytań zbyt prostych, niejasnych lub bezsensownych (np. "cześć", "ok", "asdfghjkl"), musisz zwrócić obiekt JSON z pustymi listami dla obu typów słów kluczowych.
5. **Język**: Wszystkie wyodrębnione słowa kluczowe MUSZĄ być w języku {language}. Nazwy własne (np. imiona osób, nazwy miejsc, nazwy organizacji) powinny być zachowane w oryginalnym języku.

---Przykłady---
{examples}

---Prawdziwe Dane---
Zapytanie Użytkownika: {query}

---Wyjście---
Wyjście:"""

PROMPTS["keywords_extraction_examples"] = [
    """Przykład 1:

Zapytanie: "Jak handel międzynarodowy wpływa na globalną stabilność gospodarczą?"

Wyjście:
{
  "high_level_keywords": ["Handel międzynarodowy", "Globalna stabilność gospodarcza", "Wpływ ekonomiczny"],
  "low_level_keywords": ["Umowy handlowe", "Cła", "Wymiana walut", "Import", "Eksport"]
}

""",
    """Przykład 2:

Zapytanie: "Jakie są środowiskowe konsekwencje wylesiania dla bioróżnorodności?"

Wyjście:
{
  "high_level_keywords": ["Konsekwencje środowiskowe", "Wylesianie", "Utrata bioróżnorodności"],
  "low_level_keywords": ["Wymieranie gatunków", "Niszczenie siedlisk", "Emisje dwutlenku węgla", "Las deszczowy", "Ekosystem"]
}

""",
    """Przykład 3:

Zapytanie: "Jaka jest rola edukacji w redukcji ubóstwa?"

Wyjście:
{
  "high_level_keywords": ["Edukacja", "Redukcja ubóstwa", "Rozwój społeczno-ekonomiczny"],
  "low_level_keywords": ["Dostęp do szkół", "Wskaźniki alfabetyzacji", "Szkolenia zawodowe", "Nierówność dochodowa"]
}

""",
]
