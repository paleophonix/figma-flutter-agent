final _linkRichGarbageClose = ')))])))),';
final _linkRichGarbageCloseFixed = ')))]))),';

final _logInRichGarbageReplacements = <(String, String)>[
  (
    "textScaler: textScaler,\n"
    "                            textAlign: TextAlign.left)),\n"
    "                  )))])))), Positioned(left: 58.0, child: Text('next')),",
    "textScaler: textScaler,\n"
    "                            textAlign: TextAlign.left,\n"
    "                          ),\n"
    "                        ),\n"
    "                      ),\n"
    "                    ),\n"
    "                  ),\n"
    "                ),\n"
    "              ],\n"
    "            ),\n"
    "          ),\n"
    "        ),\n"
    "      ),\n"
    "      Positioned(left: 58.0, child: Text('next')),",
  ),
  (
    "textScaler: textScaler, textAlign: TextAlign.left)),\n                  )))]))),",
    "textScaler: textScaler, textAlign: TextAlign.left)),\n                  ))), ]))),",
  ),
  (
    "textAlign: TextAlign.left)), )))]))), Positioned",
    "textAlign: TextAlign.left)), )), Positioned",
  ),
  (
    "textScaler: textScaler, textAlign: TextAlign.left)), )))]))), Positioned",
    "textScaler: textScaler, textAlign: TextAlign.left)), )), Positioned",
  ),
  (
    "textAlign: TextAlign.left))), )))])))), Positioned",
    "textAlign: TextAlign.left), Positioned",
  ),
  (
    "textAlign: TextAlign.left)), )))])))), Positioned",
    "textAlign: TextAlign.left), Positioned",
  ),
  (
    "textAlign: TextAlign.left))), )))]))), Positioned",
    "textAlign: TextAlign.left), Positioned",
  ),
  (
    "textAlign: TextAlign.left)),\n                  )))])))), Positioned(left: 58.0",
    "textAlign: TextAlign.left)),\n                  ))), ]), ), ), Positioned(left: 58.0",
  ),
  (
    "textAlign: TextAlign.left)),\n                  )))])))), Positioned(left: 58.0, child: Text('next')),",
    "textAlign: TextAlign.left)),\n                  ))), ]), ), ), Positioned(left: 58.0, child: Text('next')),",
  ),
  (
    "textAlign: TextAlign.left))),\n                  )))]))), Positioned",
    "textAlign: TextAlign.left)),\n                  )), Positioned",
  ),
  (
    "textAlign: TextAlign.left))), )))]))), Positioned",
    "textAlign: TextAlign.left)), )), Positioned",
  ),
  (
    "left)), )))])))), Positioned",
    "left)), ))), ]))), Positioned",
  ),
  (
    "left)), )))]))), Positioned",
    "left)), ))), ]))), Positioned",
  ),
  (
    ")))])), Positioned",
    "))), Positioned",
  ),
  (
    "textAlign: TextAlign.center),\n                  )))])), Positioned",
    "textAlign: TextAlign.center),\n                  )), Positioned",
  ),
];

final _extraCloseAfterCenterText = RegExp(
  r'(textAlign: TextAlign\.center\)),\s*\n\s*\)\),',
);
final _extraCloseAfterCenterTextMinified = RegExp(
  r'(textAlign: TextAlign\.center\)),\s*\)\),',
);

String fixGarbageClosersAfterLinkRich(String source) {
  var out = source;
  for (final pair in _logInRichGarbageReplacements) {
    out = out.replaceAll(pair.$1, pair.$2);
  }
  out = out.replaceAll(_linkRichGarbageClose, _linkRichGarbageCloseFixed);
  out = out.replaceAllMapped(
    _extraCloseAfterCenterText,
    (match) => '${match.group(1)}),\n                  ),',
  );
  out = out.replaceAllMapped(
    _extraCloseAfterCenterTextMinified,
    (match) => '${match.group(1)}), ),',
  );
  return out;
}
