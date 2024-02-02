# Smart-Greenhouse-ws-mqtt-solution

Ovaj programski kod predstavlja dio rješenja projekta "Pametni plastenik s kontorlom razine vlage, temperature i osvjetljenja", koji se odnosit na mrežnu stranicu i poslužiteljsku stranu.

Dio programskog rješenja koji se odnosi na implementaciju na Arduino (Croduinu) uređaju moguće je pristuptit putem sljedeće povezice: https://github.com/teakrcmar/IoT-Smart-Greenhouse.git.

## Mrežna stranica

Mrežna stranica sastoji se od dva web mjesta:

- Mjesto za prijavu korisnika (engl. _Login Page_),
- Mjesto kontrolne ploče (engl. _Dashboard Page_).

Mjesto za prijavu korisnika odogovara _login.html_ datoteki, dok mjesto kontrolne ploče odogovara _dashboard.html_ datoteci.

Rješenje je ostvarneo korištenjem HTML, CSS i JavaScript tehnologija. Budući da je program namijenjen pokretanju na Raspberry Pi uređaju korištenjem WebSocket protokola sve stilske i skriptne komponete koda su uključene u istu datoteku (nema vanjskog uključivanja stila i skripte). Stranica se pokreće pokretanjem poslužiteljske Python skripte _ws_handle.py_. Nakon pokretanja skripte, odlaskom na adresu http://[IP_adresa_uređaja]:8888 (primjer, http://localhost:8888) otvara se mjesto za prijavu korsnika. Ispravnim unosom korisničkih podataka otvara se mjesto kontrolne ploče. Važno je napomenuti da je u svakoj od datoteka (_login.html_, _dashboard.html_ i _ws_handle.py_) potrebno promijeniti vrijednost varijable "hostname" u IP adresu uređaja koji pokreće _ws_handle.py_ skriptu.

## Poslužitelj

Poslužitlejska strana treba voditi brigu o komunikaciji između mrežne stranice i Arduino uređaja korištenjem MQTT i WebSocket protokola. Također, vodi brigu o spremanju i dohvaćanju podataka iz baze podataka.
Bazu podataka je moguće implementirati lokalno na uređaju, a naredbe za stvaranje baze i tablice dostupne su u datoteci _MySQL_command.txt_. Strukura baze podataka prikazana je sljedećom slikom.

![Alt text](https://i.ibb.co/ncW11Qy/Snimka-zaslona-2024-01-26-111400.png)

Sva logika je sadržana unutar Python skripte _ws_handle.py_ čijim pokretanjem se započitanje rad sustava.
