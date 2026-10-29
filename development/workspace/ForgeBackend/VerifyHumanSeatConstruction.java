import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
import forge.*;
import forge.deck.*;
import forge.game.*;
import forge.game.card.*;
import forge.game.player.*;
import forge.gui.GuiBase;
import forge.model.FModel;

/** Actual first-controller/cached-view construction, independent of display names. */
public final class VerifyHumanSeatConstruction {
    static int checks;
    static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    static Game makeGame(String human,String bot){
        var players=List.of(new RegisteredPlayer(new Deck("Human identity fixture")).setPlayer(new ForgeLandEngine.LocalSeat(human,true)),
                            new RegisteredPlayer(new Deck("Bot identity fixture")).setPlayer(new ForgeLandEngine.LocalSeat(bot,false)));
        return new Match(new GameRules(GameType.Constructed),players,"Controller construction audit").createGame();
    }
    public static void main(String[] args)throws Exception{
        Path runtime=Path.of(args[0]).toAbsolutePath();
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime+java.io.File.separator;}});
        FModel.initialize(null,null);
        ForgeLandEngine.researchAdmission=true;
        ForgeLandEngine.fullHumanChoices=true;
        ForgeLandEngine.local=null;
        var reports=new ArrayList<Map<String,Object>>();
        for(String[] labels:List.of(new String[]{"Renamed human","Local Player"},new String[]{"Another human","Renamed human"})){
            Player previous=ForgeLandEngine.local;
            Game game=makeGame(labels[0],labels[1]);
            List<Player> players=new ArrayList<>(game.getPlayers());
            check(!players.get(0).getController().isAI(),"First installed human controller was classified as AI");
            check(!players.get(0).isAI(),"The native Forge PlayerView cached the wrong human identity");
            check(players.get(1).getController().isAI() && players.get(1).isAI(),"Bot identity changed");
            check(ForgeLandEngine.local==previous,"Factory must not overwrite the active game's global player");
            var cards=new CardCollection();
            for(String name:List.of("Plains","Island","Mountain"))cards.add(Card.fromPaperCard(FModel.getMagicDb().getCommonCards().getCard(name),players.get(0)));
            forge.util.MyRandom.setRandom(new Random(7274));
            CardCollectionView shuffled=players.get(0).getController().cheatShuffle(cards);
            check(shuffled==cards,"Human shuffle must retain the original view");
            check(shuffled.stream().map(Card::getName).toList().equals(List.of("Plains","Island","Mountain")),"AI helper reordered the human's cards");
            check(forge.util.MyRandom.getRandom().nextLong()==new Random(7274).nextLong(),"Human identity helper consumed gameplay randomness");
            reports.add(Map.of("humanLabel",labels[0],"botLabel",labels[1],"priorGamePlayerPresent",previous!=null,"passed",true));
            ForgeLandEngine.local=players.get(0); // Deliberately stale during the next game's construction.
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("passed",true,"checks",checks,"cases",reports,"scope","Actual Forge factory/PlayerView and no-op human shuffle contract; opening gameplay and original Arena response handlers are checked separately.")));
        System.out.println("Human controller factory and shuffle checks passed: "+checks);
    }
}
