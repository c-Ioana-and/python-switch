# Switch

## Scop
- acomodarea cu limbajul Python
- întelegerea modului în care funcționează un switch și implementarea sa
- cum funcționează tabela CAM și VLAN-urile
- cum se aplică STP-ul într-o rețea de switch-uri

## Implementare

Am folosit in implementare 3 dictionare declarate global:
- mac_table - pentru a retine adresa sursa MAC si portul aferent, pentru fiecare
switch in parte;
- vlan_ids - in care retin pentru fiecare interfata a switch-ului tipul acesteia:
    - T -> interfata este de tip trunk;
    - x, unde x este o valoare numerica care reprezinta ID-ul VLAN-ului din care
    face parte interfata de tip access;
- interface_states - dictionar de tip interfata/stare (LSN - listening sau BLK -
blocked).


De asemenea retin urmatoarele variabile la nivel global:
- root_bridge_ID - retine Root Bridge-ul intregii retele;
- own_bridge_ID - retin ID-ul (in cazul meu am folosit doar prioritatea ca ID)
switch-ului curent;
- root_path_cost - costul drumului pana la Root Bridge de la Own Bridge;
- root_port - retin Root Port-ul pentru switch-ul curent.

    
Functiile importante in cadrul acestei implementari:
- parse_config, in care parsez fisierul de configuratie pentru fiecare switch;
- init - initializeaza fiecare switch pentru algoritmul STP;
- populate_mac_table - umplu tabelele CAM in functie de adresa sursa, implementata
conform pseudocodului din enunt;
- change_tag - modifica pachetul primit in functie de tipul interfetelor sursa si
destinatie, adaugand tagul 802.1q la nevoie. Daca functia returneaza pachetul dar
lungimea lui este 0, inseamna ca pachetul trebuie sa fie aruncat (se incearca trimi-
terea unui pachet pe o interfata care nu este in aceeasi retea cu cea de la sursa);
- create_bdpu - creeaza un pachet BPDU (am ales sa il trimit "intreg", chiar daca
variabilele importante sunt root_bridge_ID, sender_bridge_ID si sender_path_cost);
- analyze_bpdu - analizeaza un pachet BPDU si modific starile porturilor conform
enuntului.
