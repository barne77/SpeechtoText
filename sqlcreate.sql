CREATE TABLE `taentity` (
  `idTAEntity` int(11) NOT NULL AUTO_INCREMENT,
  `DSEntitiyID` varchar(500) DEFAULT NULL,
  `DSEntiityName` varchar(500) DEFAULT NULL,
  `offset1` varchar(500) DEFAULT NULL,
  `name` varchar(1000) DEFAULT NULL,
  `text` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`idTAEntity`)
) ENGINE=InnoDB AUTO_INCREMENT=5769 DEFAULT CHARSET=utf8;

CREATE TABLE `taentityass` (
  `idtaentityass` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(1000) DEFAULT NULL,
  `offset` varchar(500) DEFAULT NULL,
  `Assertion` varchar(500) DEFAULT NULL,
  `Cond` varchar(500) DEFAULT NULL,
  `Cert` varchar(500) DEFAULT NULL,
  `Assoc` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`idtaentityass`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8;

CREATE TABLE `testoutput` (
  `idtestoutput` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(1000) DEFAULT NULL,
  `state` varchar(200) DEFAULT NULL,
  `Message` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`idtestoutput`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `testv2` (
  `channel` varchar(45) DEFAULT NULL,
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `speaker` varchar(45) DEFAULT NULL,
  `offset` varchar(45) DEFAULT NULL,
  `lexical` varchar(2000) DEFAULT NULL,
  `itn` varchar(2000) DEFAULT NULL,
  `maskedITN` varchar(2000) DEFAULT NULL,
  `display` varchar(2000) DEFAULT NULL,
  `offsetred` varchar(20) DEFAULT NULL,
  `itnred` varchar(2000) DEFAULT NULL,
  `lexicalred` varchar(2000) DEFAULT NULL,
  `textred` varchar(2000) DEFAULT NULL,
  `name` varchar(2000) DEFAULT NULL,
  `sentpos` int(11) DEFAULT NULL,
  `sentneg` int(11) DEFAULT NULL,
  `sentneu` int(11) DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=2036 DEFAULT CHARSET=utf8;

CREATE TABLE `testv2n` (
  `idtestv2n` int(11) NOT NULL AUTO_INCREMENT,
  `textredent` varchar(2000) DEFAULT NULL,
  `categoryredent` varchar(2000) DEFAULT NULL,
  `offsetredent` varchar(2000) DEFAULT NULL,
  `lengthredent` varchar(2000) DEFAULT NULL,
  `Name` varchar(1000) DEFAULT NULL,
  `offset` varchar(100) DEFAULT NULL,
  `conf` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`idtestv2n`)
) ENGINE=InnoDB AUTO_INCREMENT=435 DEFAULT CHARSET=utf8;

CREATE TABLE `testv2s` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `Name` varchar(1000) DEFAULT NULL,
  `aspect` varchar(1000) DEFAULT NULL,
  `text` varchar(2000) DEFAULT NULL,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8;

CREATE TABLE `testv2ta` (
  `idtestv2ta` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(2000) DEFAULT NULL,
  `TAEntity` varchar(45) DEFAULT NULL,
  `TANorm` varchar(45) DEFAULT NULL,
  `TACat` varchar(45) DEFAULT NULL,
  `TASCat` varchar(45) DEFAULT NULL,
  `TAOffset` varchar(45) DEFAULT NULL,
  `TACscore` varchar(45) DEFAULT NULL,
  `TASet` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`idtestv2ta`)
) ENGINE=InnoDB AUTO_INCREMENT=828 DEFAULT CHARSET=utf8;



