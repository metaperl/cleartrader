Cleartrader is a free open-source program for cash gifting.
This code is running live at [my website el camino claro](http://www.elcaminoclaro.com). 
The payout model is very similar to The Peoples Program.
However the default pay levels here are 3:

* 70%
* 20%
* 10%

whereas The Peoples Program operates on an 80-20 split.
I like the extra referral wiggle that 3 levels gives you.


# Installation

## Database

Contact me for the latest database schema

## Perl

Install the necessary CPAN modules

 Moose Mojolicious::Plugin::Authentication Mojolicious
 DBI DBIx::Array SQL::Interp
 IPC::System::Simple  autodie


### Local modules

#### Database Connectivity

##### lib/Local/DB.pm

The sub `dbh` needs to return a DBI database handle to your
database. The way I do it is by creating an instance of DBIx::DBH via
the method above and then creating the DBI dbh from there. But
that is complicated. You can simply put your connection info in the
`dbh` sub and be done. But for reference here is how I do it.

The code is not in the repo because that would reveal database
connection credentials.


```perl

package Local::DB;

use Moose;

sub dbh {
    use Local::DBIx::DBH;
    my $C = Local::DBIx::DBH->fluxflex;
    use DBI;
    my $dbh = DBI->connect( $C->for_dbi );
    warn "DBH:$dbh.";
    $dbh;
}

sub da {
    my ($self) = @_;
    use Local::DBIx::Array;
    my $dbx = Local::DBIx::Array->new;
    $dbx->dbh( $self->dbh );
    $dbx;
}

1;

```


#### lib/Local/DBIx/DBH.pm

write a method which returns and instance of DBIx::DBH with connection
parameters. Here's an example:

```perl
package Local::DBIx::DBH;

use strict;
use warnings;

use base qw(DBIx::DBH);


sub fluxflex {

    $main::sharedssl      = 'disable';
    my $port = 3306;

    my $host = 'karuna.mysql.fluxflex.com';
    my $username = 'karuna';
    my $password = 'ghOwJ266QgI';

    my $config = DBIx::DBH->new(

        username => $username,
        password => $password,

        dsn => {
            driver  => 'mysql',
            dbname  => 'karuna',
            port    => $port,
            host    => $host,
        },
        attr => { RaiseError => 1 }
    );
}

1;

```




# License

This software is freely offered for your use and the author takes no
liability for what happens when you use it.